from flask import Flask, request, Request, abort, send_file, jsonify, render_template
from functools import wraps
from werkzeug.exceptions import HTTPException
from rf2.startup import stop_server, oneclick_start_server
from rf2.status import get_server_status, get_server_mod
from rf2.interaction import do_action, Action, kick_player, chat
from rf2.deploy import deploy_server, VERSION_SUFFIX
from rf2.setup import install_server
from rf2.util import create_config
from os.path import join, exists, basename
from os import mkdir, unlink, listdir
from shutil import rmtree, unpack_archive
from json import loads, dumps
from time import sleep, time
from math import ceil
from shutil import copytree, copyfile
from sys import exit
from pathlib import Path
import hashlib
from logging import error, handlers, Formatter, getLogger, DEBUG, INFO, info
from waitress import serve
from threading import Thread, Lock
from time import sleep
import win32net
from os import getlogin
from re import match

# add hook events
# hook events call the collected hooks and manipulate the infos from the old and new status, if needed
from rf2.events.onCarCountChange import onCarCountChange
from rf2.events.onDriverPenaltyChange import onDriverPenaltyChange
from rf2.events.onSessionChange import onSessionChange
from rf2.events.onFinishStatusChange import onFinishStatusChange
from rf2.events.onPitStateChange import onPitStateChange
from rf2.events.onLowSpeed import onLowSpeed
from rf2.events.onShownFlagChange import onShownFlagChange
from rf2.events.onStart import onStart
from rf2.events.onStop import onStop
from rf2.events.onDriverSwap import onDriverSwap
from rf2.events.onNewReplay import onNewReplay
from rf2.events.onNewResult import onNewResult
from rf2.events.onNewBestLapTime import onNewBestLapTime

RECIEVER_HOOK_EVENTS = [
    onCarCountChange,
    onDriverPenaltyChange,
    onSessionChange,
    onFinishStatusChange,
    onPitStateChange,
    onLowSpeed,
    onShownFlagChange,
    onStart,
    onStop,
    onDriverSwap,
    onNewReplay,
    onNewResult,
    onNewBestLapTime,
]

# load actual hooks
import hooks

app = Flask(__name__)
recieved_status = None


def read_mod_config() -> dict:
    config = None
    if not exists("mod.json"):
        return config
    with open("mod.json", "r") as file:
        config = loads(file.read())
    return config


def read_webserver_config() -> dict:
    server_config_path = str(Path(__file__).absolute()).replace(
        "reciever.py", "server.json"
    )
    if not exists(server_config_path):
        raise Exception("Server config was not found")
    config = None
    with open(server_config_path, "r") as file:
        config = loads(file.read())
    return config


def get_server_config() -> dict:
    return {"mod": read_mod_config(), "server": read_webserver_config()}


def check_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = read_webserver_config()
        api_key = request.headers.get("Authorization")
        if not api_key or api_key != config["auth"]:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


def json_response(data) -> str:
    result = jsonify(data)
    return result


def handle_error(e):
    code = 500
    print(e)
    if isinstance(e, HTTPException):
        code = e.code
    return json_response({"error": str(e)}), code


@app.route("/oneclick_start_server", methods=["GET"])
@check_api_key
def start_oneclick():
    got = oneclick_start_server(get_server_config())
    if not got:
        raise Exception("The server could not be started")
    return json_response({"is_ok": got}), 200


last_status = None
mod_content = None
from time import time


def poll_background_status(all_hooks):
    ## WARNING: If debug is enabled, the thread may run multiple times. don't use in
    global mod_content
    new_content = get_server_mod(get_server_config())
    if new_content:
        mod_content = new_content
    while True:
        global last_status
        got = get_server_status(get_server_config())
        for event_hook in RECIEVER_HOOK_EVENTS:
            event_name = event_hook.__name__
            if got is not None and last_status is not None:
                event_hooks_to_run = (
                    all_hooks[event_name] if event_name in all_hooks else []
                )
                if "not_running" not in got:
                    try:

                        event_hook(
                            last_status,
                            got,
                            event_hooks_to_run,
                        )
                    except:
                        pass
                else:
                    if event_name == "onStop":
                        event_hook(
                            last_status,
                            got,
                            event_hooks_to_run,
                        )
        last_status = got
        sleep(1)


@app.route("/status", methods=["GET"])
def status():
    if last_status:
        last_status["mod_content"] = mod_content
    return json_response(last_status), 200


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
        abort(404)
    kick_player(get_server_config(), name)
    is_ok = True
    return json_response({"is_ok": is_ok})


@app.route("/chat", methods=["POST"])
@check_api_key
def send_message():
    message = request.form.get("message")

    if not message:
        abort(404)
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


@app.route("/deploy", methods=["POST"])
def deploy_server_config():
    if last_status is not None and "not_running" not in last_status:
        abort(403)

    config_contents = request.form.get("config")
    rfm_contents = request.form.get("rfm_config")
    if not config_contents:
        abort(404)

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
        logging.error(e)
        return json_response({"is_ok": False, "syntax_failed": False})
    except JSONDecodeError as e:
        logging.error(e)
        return json_response({"is_ok": False, "syntax_failed": True})

    soft_lock_toggle()
    # grip conditions
    grip = {}
    for key, value in request.files.items():
        grip[key] = value
    # paste the config
    with open("mod.json", "w") as config:
        config.write(config_contents)

    # reload the server config
    server_config = get_server_config()

    got = deploy_server(server_config, rfm_contents, grip)

    soft_lock_toggle()
    return json_response({"is_ok": False})


@app.route("/process_results", methods=["GET"])
def return_processed_results():
    got = process_results()
    return json_response(got)


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
        got = file.save(skinpack_path)

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
    if request.method == "POST":
        if len(request.files) == 0:
            abort(418)

    plugins = config["mod"]["plugins"]
    plugin_config_path = join(
        config["server"]["root_path"],
        "server",
        "UserData",
        "player",
        "CustomPluginVariables.JSON",
    )
    config = {}
    if exists(plugin_config_path):
        unlink(plugin_config_path)

    existing_plugins = listdir(server_bin_path)
    for plugin in existing_plugins:
        plugin_path = join(server_bin_path, plugin)
        if ".dll" in plugin_path:
            info("Removing {}".format(plugin_path))
            unlink(plugin_path)

    for file, iostream in request.files.items():
        base_name = basename(file)
        got = iostream.save(join(server_bin_path, base_name))
        info(
            "Plugin file for {} injected into ".format(
                base_name, join(server_bin_path, base_name)
            )
        )
    for plugin, overwrite in plugins.items():
        config[plugin] = overwrite
        config[plugin][" Enabled"] = 1

        info("Placing plugin {}".format(plugin))
    with open(plugin_config_path, "w") as file:
        file.write(dumps(config))
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
        abort(404)
    return send_file(
        lockfile_path, attachment_filename="ServerKeys.bin", as_attachment=True
    )


@app.route("/log", methods=["GET"])
@check_api_key
def get_log_file():
    server_config = get_server_config()
    root_path = server_config["server"]["root_path"]
    logfile_path = join(root_path, "reciever.log")
    if not exists(logfile_path):
        abort(404)
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
    print(got)
    if got is None:
        return None
    del got["mod"]["server"]
    del got["mod"]["mod"]["rfm"]
    del got["server"]

    return got


def mod_filelist():
    got = get_public_mod_info()
    if got is None:
        return []
    mod = got["mod"]["mod"]
    files = [
        join(
            "Manifests",
            "{}_{}.mft".format(mod["name"], mod["version"].replace(".", "")),
        ),
        join(
            "Installed",
            "rFm",
            "{}_{}.mas".format(mod["name"], mod["version"].replace(".", "")),
        ),
        join("Packages", "{}.rfmod".format(mod["name"])),
    ]
    has_updates = True
    for source, car in got["mod"]["cars"].items():
        if car["component"]["update"]:
            files.append(
                join(
                    "Packages",
                    "{}_v{}.rfcmp".format(
                        car["component"]["name"], car["component"]["version"]
                    ),
                )
            )
            relative_root = join(root_path, "server", "Installed", "Vehicles")
            component_path = join(
                relative_root,
                car["component"]["name"],
                car["component"]["version"],
            )
            files_of_update = listdir(component_path)
            for file in files_of_update:
                files.append(
                    join(
                        "Installed",
                        "Vehicles",
                        car["component"]["name"],
                        car["component"]["version"],
                        file,
                    )
                )
    return files


def get_name_hash(text: str) -> str:
    hash_object = hashlib.sha1(text.encode("utf8"))
    return str(hash_object.hexdigest())


@app.route("/file/<requested_hash_code>", methods=["GET"])
def get_file(requested_hash_code: str):
    config = get_server_config()
    files = mod_filelist()
    for file in files:
        hash_code = get_name_hash(file)
        if hash_code == requested_hash_code:
            full_path = join(config["server"]["root_path"], "server", file)
            filename = basename(full_path)
            return send_file(
                full_path, attachment_filename=filename, as_attachment=True
            )
    abort(404)


@app.route("/filelist", methods=["GET"])
def current_mod_filelist():
    files = mod_filelist()
    response = ""
    for file in files:
        response = response + file + ";" + get_name_hash(file) + "\n"
    return response


@app.route("/signatures", methods=["GET"])
def get_signatures():
    got = get_public_mod_info()
    if got is None:
        abort(404)
    mod = got["mod"]["mod"]
    version = mod["version"]
    name = mod["name"]
    webserver_config = read_webserver_config()
    root_path = webserver_config["root_path"]
    filename = join(
        root_path, "server", "Manifests", name + "_" + version.replace(".", "") + ".mft"
    )
    if not exists(filename):
        abort(404)
    pattern = r"(Name|Version|Type|Signature|BaseSignature)=(.+)"

    signatures = []
    mod = None
    with open(filename, "r") as file:
        lines = file.readlines()
        current_prop = {}
        for line in lines:
            print(len(line))
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

    return json_response({"mod": mod, "signatures": signatures})


@app.route("/current", methods=["GET"])
def current_mod_html():
    got = get_public_mod_info()
    if got is None:
        abort(404)
    mod = got["mod"]["mod"]
    files = mod_filelist()
    return render_template(
        "current.html",
        data=got,
        suffix=VERSION_SUFFIX,
        files=files,
    )


@app.after_request
def after_request_func(response):
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    return response


if __name__ == "__main__":
    # check for correct user
    groups = win32net.NetUserGetLocalGroups("localhost", getlogin())
    assumed_admin = False
    for group in groups:
        # the group name is dependending on the locale, but it may be sufficient for most of the cases to check for contains of "admin"
        if "admin" in group.lower():
            assumed_admin = True
            break
    if assumed_admin:
        raise Exception(
            "The reciever cannot be run as administrator. Use a dedicated user"
        )
    server_config_path = str(Path(__file__).absolute()).replace(
        "reciever.py", "server.json"
    )
    if not exists(server_config_path):
        print("{} is not present".format(server_config_path))
        create_config()
        exit(127)
    webserver_config = read_webserver_config()
    debug = webserver_config["debug"]

    root_path = webserver_config["root_path"]
    reciever_path = join(root_path, "reciever")

    manifests_target_path = join(reciever_path, "templates", "Manifests")
    installed_target_path = join(reciever_path, "templates", "Installed")

    if not exists(manifests_target_path):
        manifests_source_path = join(root_path, "server", "Manifests")
        copytree(manifests_source_path, manifests_target_path)
        print("Created manifest template")

    if not exists(installed_target_path):
        installed_source_path = join(root_path, "server", "Installed")
        copytree(installed_source_path, installed_target_path)
        print("Created installed template")
    log_path = join(root_path, "reciever.log")

    log_handler = handlers.TimedRotatingFileHandler(log_path, when="D", interval=5)
    formatter = Formatter(
        "%(asctime)s %(filename)s:%(lineno)d %(levelname)s [%(process)d]: %(message)s",
        "%b %d %H:%M:%S",
    )
    log_handler.setFormatter(formatter)
    logger = getLogger()
    logger.addHandler(log_handler)
    logger.setLevel(DEBUG if debug else INFO)
    status_thread = Thread(
        target=poll_background_status, args=(hooks.HOOKS,), daemon=True
    )
    status_thread.start()

    if debug:
        app.run(
            host=webserver_config["host"],
            port=webserver_config["port"],
            debug=debug,
        )
    else:
        serve(
            app,
            host=webserver_config["host"],
            port=webserver_config["port"],
        )
