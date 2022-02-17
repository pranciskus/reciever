from flask import Flask, request, abort, send_file, jsonify
from functools import wraps
from rf2.startup import stop_server, oneclick_start_server
from rf2.status import get_server_status, get_server_mod, is_server_up
from rf2.interaction import do_action, Action, kick_player, chat
from rf2.deploy import (
    deploy_server,
    VERSION_SUFFIX,
    update_weather,
    add_weather_client,
    update_server_only,
)
from rf2.setup import install_server
from rf2.util import create_config, get_server_port, get_public_sim_server_port
from os.path import join, exists, basename
from os import mkdir, unlink, listdir
from shutil import rmtree, unpack_archive
from json import loads, dumps
from time import sleep
from shutil import copytree
from sys import exit, argv, platform
from pathlib import Path
from waitress import serve
from threading import Thread
from os import getlogin
from re import match
import tempfile
import tarfile
from requests import get
from shutil import copyfileobj

# add hook events
# hook events call the collected hooks and manipulate the infos from the old and new status, if needed
from rf2.events.onCarCountChange import onCarCountChange
from rf2.events.onDriverPenaltyChange import (
    onDriverPenaltyChange,
    onDriverPenaltyRevoke,
    onDriverPenaltyAdd,
)
from rf2.events.onSessionChange import onSessionChange
from rf2.events.onFinishStatusChange import onFinishStatusChange
from rf2.events.onPitStateChange import (
    onPitStateChange,
    onGarageToggle,
    onPittingChange,
)
from rf2.events.onLowSpeed import onLowSpeed, onSuspectedLag
from rf2.events.onShownFlagChange import onShownFlagChange
from rf2.events.onStart import onStart
from rf2.events.onStop import onStop
from rf2.events.onDriverSwap import onDriverSwap
from rf2.events.onNewReplay import onNewReplay
from rf2.events.onNewResult import onNewResult
from rf2.events.onNewBestLapTime import onNewBestLapTime, onNewPersonalBest
from rf2.events.onLapCompleted import onLapCompleted
from rf2.events.onPositionChange import onPositionChange, onUnderYellowPositionChange
from rf2.events.onTick import onTick
from rf2.events.onDeploy import onDeploy
from rf2.events.onStateChange import onStateChange
import hooks
import logging
from logging.handlers import RotatingFileHandler

RECIEVER_HOOK_EVENTS = [
    onCarCountChange,
    onDriverPenaltyChange,
    onSessionChange,
    onFinishStatusChange,
    onPitStateChange,
    onLowSpeed,
    onShownFlagChange,
    onStart,
    onDriverSwap,
    onNewReplay,
    onNewResult,
    onNewBestLapTime,
    onNewPersonalBest,
    onLapCompleted,
    onPositionChange,
    onUnderYellowPositionChange,
    onSuspectedLag,
    onDriverPenaltyRevoke,
    onDriverPenaltyAdd,
    onGarageToggle,
    onPittingChange,
    onTick,
    onStop,
    onDeploy,
    onStateChange,
]

logging.basicConfig(
    handlers=[RotatingFileHandler("reciever.log", maxBytes=1000000, backupCount=5)],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(threadName)s [%(funcName)s]: %(message)s",
)

logger = logging.getLogger(__name__)

app = Flask(__name__)


class RecieverError(Exception):
    status_code = 418

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
        logger.error(self.message, exc_info=1)

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv


@app.errorhandler(RecieverError)
def handle_reciever_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.errorhandler(404)
def page_not_found(e):
    return json_response({"message": "Not found"}), 404


@app.after_request
def after_request_func(response):
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    return response


def read_mod_config() -> dict:
    config = None
    if not exists("mod.json"):
        return config
    with open("mod.json", "r") as file:
        config = loads(file.read())
    return config


def read_webserver_config() -> dict:
    server_config_path = str(Path(__file__).absolute()).replace(
        "reciever.py", "server.json" if platform != "linux" else "server_linux.json"
    )
    if not exists(server_config_path):
        raise Exception("Server config was not found")
    config = None
    with open(server_config_path, "r") as file:
        config = loads(file.read())

    # FIXME: temporary fix for hardcoded path
    if config.get("root_path", None) is not None:
        root_path = Path(__file__).parent.parent.absolute()
        config["root_path"] = root_path

    return config


def get_server_config() -> dict:
    return {"mod": read_mod_config(), "server": read_webserver_config()}


# FIXME: what is happening here??? Ask Gunther
def never_deployed() -> bool:
    old_config = get_server_config()
    try:
        return (
            old_config["mod"]["server"]["overwrites"]["Multiplayer.JSON"][
                "Multiplayer Server Options"
            ]["Default Game Name"]
            == "[APX] PLACEHOLDER EVENT 1337 ##"
        )
    except KeyError:
        # if we have ald broken config, treat it as never_deployed
        return False


def check_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = read_webserver_config()

        header_key = request.headers.get("Authorization", "")
        query_key = request.args.get("auth", "")

        final_key = max(header_key, query_key)

        if final_key is None or final_key != config["auth"]:
            raise RecieverError("Authenication failed")

        return f(*args, **kwargs)

    return decorated_function


def json_response(data) -> str:
    return jsonify(data)


# NOTE: is this really necessary at current project state? for real time data this kind of polling solution isn't the best
# WARNING: If debug is enabled, the thread may run multiple times. don't use in
def poll_background_status(all_hooks):

    excluded_hooks = (
        onDeploy,
        onStateChange,
    )  # hooks with special concepts, e. g. lifecycle ones

    last_status = None
    new_status = None

    while True:

        sleep(1)

        if never_deployed():
            # NOTE: nothing to do yet
            continue

        config = get_server_config()

        if not is_server_up(config):
            # NOTE: if server is not running, but we were running in previous tick - proceed
            if last_status is None or last_status.get("running") is False:
                sleep(5)
                continue

        try:
            new_status = get_server_status(config)
        except Exception as e:
            # NOTE: this shouldn't happen in any way
            logger.critical(str(e), exc_info=1)
            continue

        if last_status is None:
            last_status = new_status
            continue

        if new_status.get("skip_polling") is True:
            # NOTE: if we had trouble getting newest server data while running - skip tick
            continue

        event_hooks = set(RECIEVER_HOOK_EVENTS).difference(excluded_hooks)

        for event_hook in event_hooks:
            event_name = event_hook.__name__

            hooks_to_run = all_hooks.get(event_name, [])

            # TODO: hooks should have this check logic
            # if new_status["running"] is False and event_name != "onStop":
            #     # NOTE: if not running, run only onStop hooks
            #     logger.info("Skipping polling")
            #     continue

            try:
                event_hook(
                    last_status,
                    new_status,
                    hooks_to_run,
                )
            except Exception as e:
                logger.error(e, exc_info=1)

        last_status = new_status


# TODO: read from file last_status
@app.route("/status", methods=["GET"])
def status():

    status = get_server_status(get_server_config())

    status["mod_content"] = get_server_mod(get_server_config())

    return json_response(status), 200


@app.route("/oneclick_start_server", methods=["GET"])
@check_api_key
def start_oneclick():
    config = get_server_config()
    files = signature_build()

    got = oneclick_start_server(config, files)

    if not got:
        raise RecieverError("The server could not be started")

    return json_response({"is_ok": got}), 200


@app.route("/stop", methods=["GET"])
@check_api_key
def stop():
    return json_response({"is_ok": stop_server(get_server_config())}), 200


@app.route("/action/<action>", methods=["POST"])
@check_api_key
def action(action: str):
    is_ok = False
    for key in Action.__dict__.keys():
        if action.lower() == str(key).lower():
            do_action(get_server_config(), Action[key].value)
            is_ok = True
            break
    return json_response({"is_ok": is_ok})


@app.route("/kick", methods=["POST"])
@check_api_key
def kick():
    is_ok = False
    name = request.form.get("driver")
    if not name:
        raise RecieverError("Driver name not provided")
    kick_player(get_server_config(), name)
    is_ok = True
    return json_response({"is_ok": is_ok})


@app.route("/chat", methods=["POST"])
@check_api_key
def send_message():
    message = request.form.get("message")

    if not message:
        raise RecieverError("Message not provided")

    chat(get_server_config(), message)
    return json_response({"is_ok": True})


def soft_lock_toggle():
    config = get_server_config()
    lock_path = join(config["server"]["root_path"], "reciever", "deploy.lock")
    lock_exists = exists(lock_path)
    if lock_exists:
        unlink(lock_path)
    else:
        with open(lock_path, "w") as file:
            file.write("Nope")


@app.route("/weather", methods=["POST"])
def weather_update():

    status = get_server_status(get_server_config())

    if status is not None and status["running"] is True:
        raise RecieverError("Server is running")

    # we ignore anything except session lists
    config_contents = request.form.get("config")
    data = loads(config_contents)
    config = get_server_config()
    track = config["mod"]["track"][next(iter(config["mod"]["track"]))]
    name = track["component"]["name"]
    layout = track["layout"]
    if config["mod"]["real_weather"]:
        update_weather(config["server"]["root_path"], data["sessions"], name, layout)
    return json_response({"is_ok": False})


@app.route("/update", methods=["GET"])
@check_api_key
def update_server():
    status_hooks = (
        hooks.HOOKS["onStateChange"] if "onStateChange" in hooks.HOOKS else []
    )

    server_config = get_server_config()
    branch = server_config["mod"]["branch"]
    onStateChange(
        f"Updating to latest version for branch {branch} on Steam.", None, status_hooks
    )
    update_server_only(server_config)
    onStateChange(f"Update finished (branch: {branch})", None, status_hooks)
    return json_response({"is_ok": True})


@app.route("/deploy", methods=["POST"])
@check_api_key
def deploy_server_config():
    # only apply lock protection if the server was actually deployed once
    status_hooks = (
        hooks.HOOKS["onStateChange"] if "onStateChange" in hooks.HOOKS else []
    )

    status = get_server_status(get_server_config())

    if not never_deployed() and status is not None and status["running"] is True:
        onStateChange(
            "Deployment aborted as the server is still running", None, status_hooks
        )
        raise RecieverError("Deployment aborted as the server is still running")

    onStateChange("Deployment starting", None, status_hooks)

    config_contents = request.form.get("config")
    rfm_contents = request.form.get("rfm_config")

    if not config_contents:
        raise RecieverError("Config not provided")

    server_config = get_server_config()
    release_file_path = join(
        server_config["server"]["root_path"], "reciever", "release"
    )
    try:
        got = loads(config_contents)
        version = open(release_file_path, "r").read()
        if "comp" not in got:
            raise Exception("No compability info found. Aborting!")
        if got["comp"] != version:
            raise Exception(
                "Invalid version! The reciever expected {}, but got {}".format(
                    version, got["comp"]
                )
            )
    except Exception as e:
        raise RecieverError(str(e))

    soft_lock_toggle()
    onStateChange(
        "Locked installation to prevent double deployments", None, status_hooks
    )

    try:
        # grip conditions
        grip = {}
        for key, value in request.files.items():
            grip[key] = value
        # paste the config
        with open("mod.json", "w") as config:
            config.write(config_contents)
        # reload the server config
        server_config = get_server_config()

        onStateChange("Starting deployment", None, status_hooks)
        got = deploy_server(
            server_config, rfm_contents, grip, onStateChange, status_hooks
        )

        # track = server_config["mod"]["track"][next(iter(server_config["mod"]["track"]))]
        # name = track["component"]["name"]
        # layout = track["layout"]

        if server_config["mod"]["real_weather"]:
            onStateChange("Injecting weather plugin", None, status_hooks)
            add_weather_client(
                server_config["server"]["root_path"],
                server_config["mod"]["weather_api"],
                server_config["mod"]["weather_key"],
                server_config["mod"]["weather_uid"],
                server_config["mod"]["temp_offset"],
                False,
            )
        onStateChange("Deployment successfull", None, status_hooks)

    # TODO: whats happening here? where response if OK?
    except Exception as e:

        logger.fatal(e, exc_info=1)
        onStateChange(f"Deployment failed: {e}", None, status_hooks)

    finally:
        soft_lock_toggle()
        event_hooks_to_run = (
            hooks.HOOKS["onDeploy"] if "onDeploy" in hooks.HOOKS else []
        )
        onDeploy(None, None, event_hooks_to_run)  # call the hook

    return json_response({"is_ok": False})


@app.route("/process_results", methods=["GET"])
def return_processed_results():
    raise RecieverError("process_results() not implemented")
    # TODO: no process_results function???
    # got = process_results()
    # return json_response(got)


@app.route("/thumbs", methods=["GET"])
@check_api_key
def get_thumbs():
    config = get_server_config()
    port = get_server_port(config)
    tmpdirname = tempfile.mkdtemp(suffix="apx")
    thumb_file_path = join(tmpdirname, "apx_thumbs.tar.gz")

    entries = get("http://localhost:{}/rest/race/car".format(port)).json()
    logger.info("Using temp dir {} for thumbnails".format(tmpdirname))
    try:
        with tarfile.open(thumb_file_path, "w:gz") as tar:
            for entry in entries:
                image = entry["image"]
                car_id = entry["id"]
                image_url = "http://localhost:{}".format(port) + image
                r = get(image_url, stream=True)
                if r.status_code == 200:
                    image_path = join(tmpdirname, car_id + ".png")
                    with open(image_path, "wb") as f:
                        r.raw.decode_content = True
                        copyfileobj(r.raw, f)
                        tar.add(image_path, car_id + ".png")
                    unlink(image_path)
            tar.close()
        return send_file(thumb_file_path, attachment_filename="skins.tar.gz")
    except Exception as e:
        raise RecieverError(str(e))


@app.route("/skins", methods=["POST"])
@check_api_key
def get_skins():
    config = get_server_config()
    build_path = join(config["server"]["root_path"], "build")
    if request.method == "POST":
        if "skins" not in request.files or "target_path" not in request.form:
            abort(418)
        file = request.files["skins"]
        skinpack_path = join(build_path, file.filename)
        file.save(skinpack_path)

        target_path = join(build_path, request.form.get("target_path"))
        if exists(target_path):
            rmtree(target_path)
        mkdir(target_path)

        unpack_archive(skinpack_path, target_path)
        unlink(skinpack_path)
    return json_response({"is_ok": True})


@app.route("/plugins", methods=["POST"])
@check_api_key
def install_plugins():
    config = get_server_config()
    server_bin_path = join(config["server"]["root_path"], "server", "Bin64", "Plugins")
    paths = loads(request.form.get("paths"))
    if request.method == "POST":
        if len(request.files) == 0:
            abort(418)

    plugins = config["mod"]["plugins"]
    real_weather = config["mod"]["real_weather"]
    plugin_config_path = join(
        config["server"]["root_path"],
        "server",
        "UserData",
        "player",
        "CustomPluginVariables.JSON",
    )
    plugin_config = {}
    if exists(plugin_config_path):
        unlink(plugin_config_path)

    existing_plugins = listdir(server_bin_path)
    for plugin in existing_plugins:
        plugin_path = join(server_bin_path, plugin)
        if ".dll" in plugin_path:
            if real_weather and "rf2WeatherPlugin" in plugin_path:
                app.logger.info(
                    "NOT Removing {} as this is needed by the real weather injection.".format(
                        plugin_path
                    )
                )
            else:
                app.logger.info("Removing {}".format(plugin_path))
                unlink(plugin_path)

    for file, iostream in request.files.items():
        base_name = basename(file)
        if base_name in paths:
            app.logger.info(
                "The plugin file {} has a different path. We will use this path: {}".format(
                    base_name, paths[base_name]
                )
            )
            target_path = join(
                config["server"]["root_path"], "server", paths[base_name]
            )
            if not exists(target_path):
                Path(target_path).mkdir(parents=True, exist_ok=True)
                app.logger.info(f"Created path {target_path} as it was not existing")
            else:
                app.logger.info(f"Path {target_path} exists and will not be cleaned")

            iostream.save(join(target_path, base_name))
            app.logger.info(
                "Plugin file for {} injected into {}".format(
                    base_name, join(target_path, base_name)
                )
            )
        else:
            iostream.save(join(server_bin_path, base_name))
            app.logger.info(
                "Plugin file for {} injected into {}".format(
                    base_name, join(server_bin_path, base_name)
                )
            )
    for plugin, overwrite in plugins.items():
        if ".dll" in plugin.lower():
            plugin_config[plugin] = overwrite
            plugin_config[plugin][" Enabled"] = 1
            app.logger.info(
                "Placing plugin {} into CustomPluginVariables.JSON".format(plugin)
            )
        else:
            app.logger.info(
                f"The file {plugin} is not a DLL file, we won't add it into CustomPluginVariables.JSON"
            )
    if real_weather:
        plugin_config["rf2WeatherPlugin.dll"] = {
            " Enabled": 1,
            "LOG": 0,
            "UID": config["mod"]["weather_uid"],
        }
    with open(plugin_config_path, "w") as file:
        file.write(dumps(plugin_config))
    return json_response({"is_ok": True})


@app.route("/install", methods=["GET"])
def initial_setup():
    got = install_server(get_server_config())
    return json_response({"is_ok": got})


@app.route("/lockfile", methods=["GET"])
def get_lockfile():
    server_config = get_server_config()
    root_path = server_config["server"]["root_path"]
    lockfile_path = join(root_path, "server", "UserData", "ServerKeys.bin")
    if not exists(lockfile_path):
        raise RecieverError(f"Lockfile not found in {lockfile_path}")
    return send_file(
        lockfile_path, attachment_filename="ServerKeys.bin", as_attachment=True
    )


@app.route("/log", methods=["GET"])
@check_api_key
def get_log_file():
    server_config = get_server_config()
    root_path = server_config["server"]["root_path"]
    logfile_path = join(root_path, "reciever", "reciever.log")
    if not exists(logfile_path):
        raise RecieverError(f"Log file not found in {logfile_path}")
    return send_file(
        logfile_path, attachment_filename="reciever.log", as_attachment=True
    )


@app.route("/unlock", methods=["POST"])
def initial_setup_unlock():
    if request.method == "POST":
        if "unlock" not in request.files:
            abort(418)
        file = request.files["unlock"]
        server_config = get_server_config()
        root_path = server_config["server"]["root_path"]
        unlock_path = join(root_path, "server", "UserData", "ServerUnlock.bin")
        file.save(unlock_path)
        return "ok"
    return "fail"


def get_public_mod_info():
    got = get_server_config()
    got["port"] = get_public_sim_server_port(got)
    if got is None:
        return None
    del got["mod"]["server"]
    del got["server"]
    del got["mod"]["callback_target"]
    del got["mod"]["conditions"]

    return got


def get_files_of_update(component: str, version: str):
    config = get_server_config()
    mod = config["mod"]
    webserver_config = read_webserver_config()
    root_path = webserver_config["root_path"]

    cars = mod["cars"]
    for _, car in cars.items():
        car_component = car["component"]["name"]
        car_version = car["component"]["version"]
        if component == car_component and version == car_version:
            path = join(
                root_path, "server", "Installed", "Vehicles", component, version
            )
            files = listdir(path)
            return files
    return []


@app.route(
    "/files/<component>/<version>/<file>", methods=["GET"]
)  # supports ONLY cars at the moment
def get_file(component: str, version: str, file: str):
    config = get_server_config()
    mod = config["mod"]
    webserver_config = read_webserver_config()
    root_path = webserver_config["root_path"]

    cars = mod["cars"]
    for _, car in cars.items():
        car_component = car["component"]["name"]
        car_version = car["component"]["version"]
        car_update = car["component"]["update"]
        if car_update:
            if component == car_component and version == car_version:
                path = join(
                    root_path,
                    "server",
                    "Installed",
                    "Vehicles",
                    component,
                    version,
                    file,
                )
                if exists(path):
                    return send_file(path)
    raise RecieverError(f"Unable to send a file to {path}")


@app.route("/mod", methods=["GET"])
def get_mod():
    got = get_public_mod_info()
    return json_response(got)


@app.route("/download", methods=["GET"])
def download_files():

    webserver_config = read_webserver_config()
    root_path = webserver_config["root_path"]

    output_filename = join(root_path, "modpack.tar.gz")

    return send_file(
        output_filename, attachment_filename="modpack.tar.gz", as_attachment=True
    )


def signature_build():
    # FIXME: why two same calls?
    raw_mod = get_public_mod_info()
    got = get_public_mod_info()

    if got is None:
        raise RecieverError("Mod info not found")

    mod = got["mod"]["mod"]
    version = mod["version"]
    name = mod["name"]
    webserver_config = read_webserver_config()
    root_path = webserver_config["root_path"]
    filename = join(
        root_path, "server", "Manifests", name + "_" + version.replace(".", "") + ".mft"
    )

    if not exists(filename):
        raise RecieverError(f"Manifest file not found {filename}")

    pattern = r"(Name|Version|Type|Signature|BaseSignature)=(.+)"

    signatures = []
    mod = None
    with open(filename, "r") as file:
        lines = file.readlines()
        current_prop = {}
        for line in lines:
            if len(line) == 1:
                if current_prop != {}:
                    if mod is None:
                        mod = current_prop
                    else:
                        signatures.append(current_prop)
                    current_prop = {}

            got = match(pattern, line)
            if got:
                key = got.group(1)
                value = got.group(2)
                current_prop[key] = value

    mod["suffix"] = VERSION_SUFFIX
    car_haystack = raw_mod["mod"]["cars"]
    track_haystack = raw_mod["mod"]["track"]
    for _, props in enumerate(signatures):

        name = props["Name"]
        version = props["Version"]
        origin_component = None
        is_vehicle = int(props["Type"]) == 2
        haystack = car_haystack if is_vehicle else track_haystack
        props["source"] = None
        for workshop_id, mod_props in haystack.items():
            comp_name = mod_props["component"]["name"]
            comp_version = mod_props["component"]["version"]
            if name == comp_name and version == comp_version:
                origin_component = mod_props
                origin_component["steamid"] = workshop_id
                props["source"] = workshop_id

                if VERSION_SUFFIX in comp_version:
                    props["files"] = get_files_of_update(comp_name, comp_version)

    return {"mod": mod, "signatures": signatures}


@app.route("/signatures", methods=["GET"])
def get_signatures():
    return json_response(signature_build())


if __name__ == "__main__":

    # check for correct user
    if platform == "win32":
        import win32net

        groups = win32net.NetUserGetLocalGroups("localhost", getlogin())
        assumed_admin = False
        for group in groups:
            # the group name is dependending on the locale, but it may be sufficient to check for contains of "admin"
            if "admin" in group.lower():
                assumed_admin = True
                break
        if assumed_admin and "--admin" not in argv:
            raise Exception(
                "The reciever cannot be run as administrator. Use a dedicated user"
            )

    # debug only: add a new server.json per argv
    server_config_path = str(Path(__file__).absolute()).replace(
        "reciever.py", "server.json" if platform != "linux" else "server_linux.json"
    )

    # TODO: ????
    if not exists(server_config_path):
        logger.error("{} is not present".format(server_config_path))
        create_config()
        exit(127)

    webserver_config = read_webserver_config()
    debug = webserver_config["debug"]

    logger.info(f"Server config: {webserver_config}")

    root_path = webserver_config["root_path"]
    reciever_path = join(root_path, "reciever")

    # TODO: quit if no Mainifests??? refactor as a function
    manifests_source_path = join(root_path, "server", "Manifests")
    manifests_target_path = join(reciever_path, "templates", "Manifests")
    if not exists(manifests_target_path):
        logger.info(f"Copying Manifests from: {manifests_source_path}")
        try:
            copytree(manifests_source_path, manifests_target_path)
            logger.info(f"Created Manifests in: {manifests_target_path}")
        except FileNotFoundError as e:
            logger.error(f"Failed to copy Manifests. Reason: {str(e)}")
    else:
        logger.info(f"Manifests found in: {manifests_target_path}")

    # TODO: quit if no Installed??? refactor as a function
    installed_source_path = join(root_path, "server", "Installed")
    installed_target_path = join(reciever_path, "templates", "Installed")
    if not exists(installed_target_path):
        logger.info(f"Copying Installed from: {installed_source_path}")
        try:
            copytree(installed_source_path, installed_target_path)
            logger.info(f"Created Installed in: {installed_target_path}")
        except FileNotFoundError as e:
            logger.error(f"Failed to copy Installed. Reason: {str(e)}")
    else:
        logger.info(f"Installed found in: {installed_target_path}")

    try:
        logger.info("Starting background polling process")
        status_thread = Thread(
            target=poll_background_status, args=(hooks.HOOKS,), daemon=True
        )
        status_thread.start()

        if debug:
            logger.info("Starting flask dev server")
            app.run(
                host=webserver_config["host"],
                port=webserver_config["port"],
                debug=debug,
            )
        else:
            logger.info("Starting flask prod server")
            serve(
                app,
                host=webserver_config["host"],
                port=webserver_config["port"],
            )

    except Exception as e:
        logger.error(e, exc_info=1)
