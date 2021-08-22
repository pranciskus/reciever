from os.path import join, exists, basename, pathsep, dirname
from os import listdir, mkdir, getenv, unlink, stat
from shutil import copy, rmtree, copytree, move
from rf2.steam import run_steamcmd, install_mod
import subprocess
from time import sleep
from json import loads, dumps, load, dump
import re
from distutils.version import LooseVersion
import logging
from rf2.steam import get_entries_from_mod
from rf2.util import get_server_port
from datetime import datetime

VERSION_SUFFIX = ".9apx"


def deploy_server(
    server_config: dict, rfm_contents: str, grip_data, onStateChange, status_hooks
) -> bool:
    logging.info("Starting server deploy")
    vehicles = server_config["mod"]["cars"]
    tracks = server_config["mod"]["track"]
    suffix = server_config["mod"]["suffix"]
    global VERSION_SUFFIX
    if suffix:
        VERSION_SUFFIX = suffix
        logging.info(f"Using {suffix} as version label")
    else:
        VERSION_SUFFIX = ".9apx"  # to reset between builds

    mod_info = server_config["mod"]["mod"]
    if "%" in VERSION_SUFFIX:
        now = datetime.now()
        VERSION_SUFFIX = now.strftime(VERSION_SUFFIX)
        server_config["mod"]["suffix"] = VERSION_SUFFIX
        logging.info("The package suffix was parsed to {}".format(VERSION_SUFFIX))

    if "%" in mod_info["version"]:
        now = datetime.now()
        mod_info["version"] = now.strftime(mod_info["version"])
        server_config["mod"]["mod"]["version"] = mod_info["version"]
        logging.info("The mod version was parsed to {}".format(mod_info["version"]))

    if "%" in VERSION_SUFFIX or "%" in mod_info["version"]:
        onStateChange("Create conditions failed", str(e), status_hooks)
        logging.error(
            "{} or {} was parsed not valid".format(VERSION_SUFFIX, mod_info["version"])
        )
        raise Exception(
            "{} or {} was parsed not valid".format(VERSION_SUFFIX, mod_info["version"])
        )

    conditions = (
        server_config["mod"]["conditions"]
        if "conditions" in server_config["mod"]
        else None
    )
    root_path = server_config["server"]["root_path"]

    event_config = server_config["mod"]
    onStateChange("Restoring vanilla state and doing Steam update", None, status_hooks)
    restore_vanilla(server_config)
    # build vehicle mods
    for workshop_id, vehicle in vehicles.items():
        if int(workshop_id) > 0:
            # if the workshop id is present, attempt install
            onStateChange("Installing workshop item", workshop_id, status_hooks)
            run_steamcmd(server_config, "add", workshop_id)
        component_info = vehicle["component"]
        update = component_info["update"]
        official = component_info["official"]

        if update and official:
            logging.info(
                "Requested update on top of component {} which is marked as official content. Selecting latest-even version".format(
                    component_info["name"]
                )
            )
            component_info["version"] = "latest-even"

        install_mod(server_config, int(workshop_id), component_info["name"])
        onStateChange("Installing vehicle", component_info["name"], status_hooks)
        if component_info["update"]:
            create_mas(server_config, component_info, True)
            build_cmp_mod(server_config, component_info, "Vehicles", True)
            onStateChange(
                "Creating cmp mod for vehicle", component_info["name"], status_hooks
            )

    used_track = None
    for workshop_id, track in tracks.items():
        used_track = track
        if int(workshop_id) > 0:
            # if the workshop id is present, attempt install
            onStateChange("Installing workshop item", workshop_id, status_hooks)
            run_steamcmd(server_config, "add", workshop_id)

        onStateChange("Installing track", track["component"]["name"], status_hooks)
        install_mod(server_config, int(workshop_id), track["component"]["name"])
        component_info = track["component"]
        update = component_info["update"]
        official = component_info["official"]

        if update and official:
            logging.info(
                "Requested update on top of component {} which is marked as official content. Selecting latest-even version".format(
                    component_info["name"]
                )
            )
            component_info["version"] = "latest-even"

        if component_info["update"]:
            create_mas(server_config, component_info, True, False)
            try:
                build_cmp_mod(server_config, component_info, "Locations", True)
                onStateChange(
                    "Creating cmp mod for track", component_info["name"], status_hooks
                )
            except Exception as e:
                print(e)
        try:

            onStateChange("Create conditions", None, status_hooks)
            create_conditions(
                root_path,
                grip_data,
                conditions,
                track["component"]["name"],
                track["layout"],
                server_config["mod"]["sessions"],
            )
        except Exception as e:
            onStateChange("Create conditions failed", str(e), status_hooks)
            import traceback

            traceback.print_exc()
            print("Error", e)

    onStateChange(
        "Building event",
        "{} {}".format(mod_info["name"], mod_info["version"]),
        status_hooks,
    )
    build_mod(server_config, vehicles, used_track, mod_info, rfm_contents)

    # set real versions
    for _, vehicle in event_config["cars"].items():
        version = vehicle["component"]["version"]
        name = vehicle["component"]["name"]
        if version == "latest" or version == "latest-even":
            # use the latest one or the lastest even version
            version = get_latest_version(
                join(root_path, "server", "Installed", "Vehicles", name),
                version == "latest",
            )
        vehicle["component"]["version"] = version

    for _, track in event_config["track"].items():
        version = track["component"]["version"]
        name = track["component"]["name"]
        if version == "latest" or version == "latest-even":
            # use the latest one or the lastest even version
            version = get_latest_version(
                join(root_path, "server", "Installed", "Locations", name),
                version == "latest",
            )
        track["component"]["version"] = version
    path = join(root_path, "reciever", "mod.json")
    onStateChange("Placed mod.json", None, status_hooks)
    logging.info("Placing updated mod.json")
    with open(path, "w") as file:
        file.write(dumps(event_config))

    # adjust settings length

    multiplayer_json_path = join(
        root_path, "server", "UserData", "player", "Multiplayer.JSON"
    )
    player_json_path = join(root_path, "server", "UserData", "player", "player.JSON")
    multiplayer_json = None
    player_json = None

    with open(player_json_path, "r") as file:
        player_json = load(file)

    with open(multiplayer_json_path, "r") as file:
        multiplayer_json = load(file)

    for session in event_config["sessions"]:
        type = session["type"]
        length = session["length"]
        laps = session["laps"]
        start = session["start"]
        time_after_midnight = None
        onStateChange("Adding session", session["type"], status_hooks)
        if start and ":" in start:
            time_parts = start.split(":")
            time_after_midnight = int(time_parts[0]) * 60 + int(time_parts[1])

            onStateChange(
                "Changing start time for session",
                session["type"] + ": " + session["start"],
                status_hooks,
            )
            logging.info(
                "Session {} will recieve a start time: {} -> {} minutes after midnight".format(
                    type, start, time_after_midnight
                )
            )

        if "P" in type and "1" not in type:
            logging.warn("Due to unclear configuration, only Practice 1 is allowed")
            raise Exception("Due to unclear configuration, only Practice 1 is allowed")

        if type == "P1" and laps > 0 and length == 0:
            # if laps are set for practice, cause an error
            logging.warn("Only time length is allowed for practice")
            raise Exception("Only time length is allowed for practice")

        if type == "P1":
            # set practice 1 length
            if time_after_midnight:
                player_json["Race Conditions"][
                    "Practice1StartingTime"
                ] = time_after_midnight
            multiplayer_json["Multiplayer Server Options"]["Practice 1 Time"] = length

        if type == "Q1":
            if time_after_midnight:
                player_json["Race Conditions"][
                    "QualifyingStartingTime"
                ] = time_after_midnight
            if laps == 0:
                multiplayer_json["Multiplayer Server Options"]["Qualifying Laps"] = 255

            multiplayer_json["Multiplayer Server Options"]["Qualifying Laps"] = laps
            multiplayer_json["Multiplayer Server Options"]["Qualifying Time"] = length

        if type == "WU":
            if time_after_midnight:
                player_json["Race Conditions"][
                    "WarmupStartingTime"
                ] = time_after_midnight
            player_json["Race Conditions"]["Run Warmup"] = True
            multiplayer_json["Multiplayer Server Options"]["Warmup Time"] = length

        if type == "R1":
            # race settings
            if time_after_midnight:
                player_json["Race Conditions"][
                    "MULTI RaceStartingTime"
                ] = time_after_midnight
            # Insert starting type, if a race session is present
            player_json["Race Conditions"]["MULTI Formation Lap"] = event_config[
                "start_type"
            ]
            if laps > 0:
                player_json["Game Options"]["MULTI Race Finish Criteria"] = 1
                player_json["Game Options"]["MULTI Race Laps"] = laps
            else:
                player_json["Game Options"]["MULTI Race Finish Criteria"] = 2
                player_json["Game Options"]["MULTI Race Time"] = length

    onStateChange("Updating player.json", None, status_hooks)
    with open(player_json_path, "w") as file:
        logging.info("Updating player.json to represent session dimensions")
        dump(player_json, file, indent=4, separators=(",", ": "))

    onStateChange("Updating multiplayer.json", None, status_hooks)
    with open(multiplayer_json_path, "w") as file:
        logging.info("Updating multiplayer.json to represent session dimensions")
        dump(multiplayer_json, file, indent=4, separators=(",", ": "))

    logging.info("Finished server deploy")

    onStateChange("Deployment finished successfully", None, status_hooks)
    return True


def update_weather(root_path: str, sessions: list, mod_name, layout):
    properties = find_location_properties(root_path, mod_name, layout)

    server_root = join(root_path, "server")
    condition_files_root_path = join(server_root, "UserData", "player", "Settings")
    weather_file_parent = join(condition_files_root_path, properties["SettingsFolder"])
    weather_file_path = join(
        weather_file_parent, properties["WET"].replace(".WET", "s.WET")
    )
    verbose_titles = {
        "P1": "Practice Info",
        "Q1": "Qualifying Info",
        "R1": "Race Info",
    }
    weather_template = properties["WET_SOURCE"]
    logging.info(f"Using the file {weather_template} to generate weather information")

    with open(weather_template, "r") as weather_file:
        content = weather_file.read()
        # get head of weather file
        altered_content = []
        for line in content.splitlines():
            # we assume this is the first block
            if "[Practice Info]" in line:
                break
            altered_content.append(line)

        weather_present = False
        for session_type in ["P1", "Q1", "R1"]:
            for session in sessions:
                type = session["type"]
                weather = session["weather"]
                if type == session_type and weather:
                    weather_present = True
                    verbose_title = verbose_titles[type]
                    altered_content.append(f"[{verbose_title}]")
                    lines = weather.splitlines()
                    for line in lines:
                        altered_content.append(line)
                    altered_content.append("")
        with open(weather_file_path, "w") as weather_write_handle:
            for line in altered_content:
                weather_write_handle.write(line + "\n")
        if weather_present:
            # update server config
            player_json = {}
            player_json_path = join(
                root_path, "server", "UserData", "player", "player.JSON"
            )
            with open(player_json_path, "r") as file:
                player_json = load(file)

            player_json["Race Conditions"]["CHAMP Weather"] = 5
            player_json["Race Conditions"]["CURNT Weather"] = 5
            player_json["Race Conditions"]["GPRIX Weather"] = 5
            player_json["Race Conditions"]["MULTI Weather"] = 5

            with open(player_json_path, "w") as file:
                logging.info("Updating player.json to represent weather data")
                dump(player_json, file, indent=4, separators=(",", ": "))


def create_conditions(
    root_path: str, grip, conditions, mod_name: str, layout: str, sessions: list
) -> bool:
    server_root = join(root_path, "server")
    if conditions is None:
        # conditions may be not configured at all
        logging.info("Omitting grip injection as there is nothing submitted")
        return True

    properties = find_location_properties(root_path, mod_name, layout)
    if properties is None:
        logging.warning(
            "No properties could be extracted from the track. Make sure you are using a correct layout description for this component."
        )

    condition_files_root_path = join(server_root, "UserData", "player", "Settings")
    weather_file_parent = join(condition_files_root_path, properties["SettingsFolder"])
    if not exists(weather_file_parent):
        mkdir(weather_file_parent)
    weather_file_path = join(
        weather_file_parent, properties["WET"].replace(".WET", "s.WET")
    )
    weather_template = properties["WET_SOURCE"]
    extraction_path = dirname(properties["GDB_SOURCE"])
    extraction_path_files = listdir(extraction_path)
    with open(weather_template, "r") as weather_file:
        content = weather_file.read()
        for key, value in grip.items():
            content = re.sub(
                r"RealRoad{}=\".+\"".format(key),
                'RealRoad{}="user:{}"'.format(key, key + ".rrbin"),
                content,
            )
            grip_file_path = join(weather_file_parent, key + ".rrbin")
            value.save(grip_file_path)
        for session in sessions:
            type = session["type"]
            grip_needle = session["grip_needle"]
            if grip_needle:
                for file in extraction_path_files:
                    lower_file = file.lower()
                    if ".rrbin" in lower_file and grip_needle in lower_file:
                        logging.info(
                            "Session {} will use preset grip file {}".format(type, file)
                        )
                        content = re.sub(
                            r"RealRoad{}=\".+\"".format(type),
                            'RealRoad{}="preset:{}"'.format(type, file),
                            content,
                        )
            else:
                logging.info("Session {} will not use preset grip files".format(type))

        with open(weather_file_path, "w") as weather_write_handle:
            weather_write_handle.write(content)
    return True


def get_latest_version(root_path: str, latest=True) -> str:
    versions = listdir(root_path)
    if len(versions) == 1:
        logging.info(
            "We don't need to sort here as only one version ({}) is available. Falling back.".format(
                versions[0], root_path
            )
        )
        return versions[0]
    version_sort_failed = False
    try:
        versions.sort(key=LooseVersion)
    except:
        versions = True
        logging.error("Version sort failed. Falling back to filesystem sorting")
        versions.sort()
    if len(versions) == 0:
        raise Exception("There are no versions to choose from")
    if latest:
        logging.warning(
            "You are using latest version for component inside {}. If updates are relying on that, this may cause issues.".format(
                root_path
            )
        )
    if not latest:
        versions.reverse()
        for version in versions:
            match = re.match(r"\d+\.(\d+)", version).group(1)
            if int(match) % 2 == 0:
                return version
        raise Exception("No suitable version found")
    else:
        version = versions[-1]
    return version


def build_mod(
    server_config: dict, vehicles: dict, track: dict, mod_info: dict, rfm_contents: str
):
    root_path = server_config["server"]["root_path"]
    data = ""
    with open("templates/pkginfo.dat") as f:
        data = f.read()

    veh_contents = ""
    for _, vehicle in vehicles.items():
        component = vehicle["component"]
        name = component["name"]
        version = component["version"]

        # version == latest -> choose "latest" available version
        if version == "latest" or version == "latest-even":
            # use the latest one or the lastest even version
            version = get_latest_version(
                join(root_path, "server", "Installed", "Vehicles", name),
                version == "latest",
            )
            logging.info(f"Using {version} as mod version for item {name}")
            print("Using", version, "as mod version for item", name)

        line = 'Vehicle="' + name + " v" + version + ',0"'
        if len(vehicle["entries"]) > 0:
            for entry in vehicle["entries"]:
                # as the entry contains the pit group -> get rid of it
                line = line + ' "' + entry.split(":")[0] + ',1"'
        else:
            entries = get_entries_from_mod(root_path, name, version)
            for entry in entries:
                line = line + ' "' + entry + ',1"'

        if server_config["mod"]["include_stock_skins"]:
            base_version = version.replace(VERSION_SUFFIX, "")

            logging.info(
                f"The event demands to include stock skins from {name} {base_version}"
            )
            entries = get_entries_from_mod(root_path, name, base_version)
            for entry in entries:
                line = line + ' "' + entry + ',1"'

        veh_contents = veh_contents + line + "\n"

    # multiple tracks are not supported
    track_components = track["component"]

    if (
        track_components["version"] == "latest"
        or track_components["version"] == "latest-even"
    ):
        track_components["version"] = get_latest_version(
            join(
                root_path, "server", "Installed", "Locations", track_components["name"]
            ),
            track_components["version"] == "latest",
        )
        print(
            "Using",
            track_components["version"],
            "as mod version for item",
            track_components["name"],
        )

    replacements = {
        "mod_name": mod_info["name"],
        "mod_version": mod_info["version"],
        "trackmod_name": track_components["name"],
        "trackmod_version": "v" + track_components["version"],
        "layouts": '"' + track["layout"] + ',1"',
        "location": join(root_path, "server", "Packages", mod_info["name"] + ".rfmod"),
        "veh_mods_count": str(len(vehicles)),
        "veh_mod_contents": veh_contents,
        "build_path": join(root_path, "build"),
    }
    for key, value in replacements.items():
        data = data.replace("#" + key, value)

    pkg_info_path = join(root_path, "reciever", "pkginfo.dat")
    # write data
    with open(pkg_info_path, "w") as cmp_write:
        cmp_write.write(data)

    # build rfm mas
    rfm_build_path = join(root_path, "build", mod_info["name"] + "_rfm")
    if exists(rfm_build_path):
        rmtree(rfm_build_path)
    mkdir(rfm_build_path)
    copy("templates/rFm/icon.dds", join(rfm_build_path, "icon.dds"))
    copy("templates/rFm/smicon.dds", join(rfm_build_path, "smicon.dds"))
    with open(join(rfm_build_path, "default.rfm"), "w") as rFm_write:
        rFm_write.write(rfm_contents)

    rfm_mas_path = join(root_path, "build", mod_info["name"] + ".mas")
    rfmod_path = join(root_path, "server", "Packages", mod_info["name"] + ".rfmod")
    build_mas(server_config, rfm_build_path, rfm_mas_path)
    server_root_path = join(root_path, "server")
    run_modmgr_build(server_root_path, pkg_info_path)
    run_modmgr_install(server_root_path, rfmod_path)
    if not exists(rfmod_path) or stat(rfmod_path).st_size == 0:
        logging.fatal(
            "The deployment failed. The mod is either not existing or empty. Check your keys and rfm settings."
        )
        raise Exception("Deployment failed")


def run_modmgr_build(server_root_path: str, pkg_info_path: str):
    modmgr_path = join(server_root_path, "Bin64\\ModMgr.exe")
    cmd_line = [
        modmgr_path,
        f"-c{server_root_path}",
        f"-b{pkg_info_path}",
        "0",
    ]

    logging.info("Running modmgr build {}".format(cmd_line))
    build = subprocess.Popen(
        cmd_line,
        shell=False,
        cwd=server_root_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return_code = build.wait()

    logging.info(
        "ModMgr command {} returned error code {}".format(cmd_line, return_code)
    )


def run_modmgr_install(server_root_path: str, pkg_path: str):
    sleep(2)  # TODO: Make sure install actions are actually done
    modmgr_path = join(server_root_path, "Bin64\\ModMgr.exe")
    cmd_line = [
        modmgr_path,
        f"-c{server_root_path}",
        "-q",
        f"-i{pkg_path}",
    ]
    logging.info("Running modmgr install {}".format(cmd_line))
    build = subprocess.Popen(
        cmd_line, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return_code = build.wait()
    logging.info(
        "ModMgr command {} returned error code {}".format(cmd_line, return_code)
    )


def build_cmp_mod(
    server_config,
    component_info: dict,
    packageType: str = "Vehicles",
    add_version_suffix=False,
):
    root_path = server_config["server"]["root_path"]
    name = component_info["name"]
    version = component_info["version"]

    if version == "latest" or version == "latest-even":
        # use the latest one or the lastest even version
        version = get_latest_version(
            join(root_path, "server", "Installed", packageType, name),
            version == "latest",
        )

    update_version = version + VERSION_SUFFIX

    base_target_path = join(
        root_path, f"server\\Installed\\{packageType}\\{name}\\{version}"
    )
    target_path = join(
        root_path, f"server\\Installed\\{packageType}\\{name}\\{update_version}"
    )

    if not add_version_suffix:
        mas_path = join(root_path, "build", f"{name}.mas")
    else:
        mas_path = join(root_path, "build", f"{name}_v{version}{VERSION_SUFFIX}.mas")

    # inject dat in cmpinfo
    data = ""
    with open("templates/cmpinfo.dat") as f:
        data = f.read()
    # replace values from parameters
    # TODO LOCATION -> MAYBE THE LOCATION IN PACKAGES (fullpath)
    location_path = join(root_path, f"server\\Packages\\{name}_v{update_version}.rfcmp")
    data = (
        data.replace("component_name", name)
        .replace("mod_version", update_version)
        .replace("base_version", version)
        .replace("mas_file", mas_path)
        .replace("location", location_path)
        .replace("mod_download_url", "")
    )
    if packageType == "Locations":
        data = data.replace("Type=2", "Type=1")

    cmp_file = join(root_path, "reciever", "cmpinfo.dat")
    with open(cmp_file, "w") as cmp_write:
        cmp_write.write(data)

    logging.info("Created cmpinfo file in {}".format(cmp_file))
    run_modmgr_build(join(root_path, "server"), cmp_file)
    run_modmgr_install(join(root_path, "server"), location_path)
    return exists(target_path)


def restore_vanilla(server_config: dict) -> bool:
    """
    Restores the server to a vanilla state.
    The server will copy template folders (installed, packages) and files (player.json, multiplayer.json) in the server
    Steam folders will be deleted aswell
    The server will be updated to the latest steam available version.

    Args:
        server_config: The global configuration for this instance

    Returns:
        The success of the operation
    """
    root_path = server_config["server"]["root_path"]
    server_root_path = join(root_path, "server")
    reciever_root_path = join(root_path, "reciever")

    # remove steam workshop items
    steam_packages_path = join(
        server_root_path, "steamapps", "workshop", "content", "365960"
    )
    if exists(steam_packages_path):
        logging.info("Removed tree in {}".format(steam_packages_path))
        rmtree(steam_packages_path)

    # Overwrite player.json and multiplayer.json
    user_data_path = join(server_root_path, "UserData")
    profile_path = join(user_data_path, "player")
    copied_player = copy(
        join(reciever_root_path, "templates", "player.JSON"),
        join(profile_path, "player.JSON"),
    )
    copy(
        join(reciever_root_path, "templates", "Multiplayer.JSON"),
        join(profile_path, "Multiplayer.JSON"),
    )
    plugin_json_path = join(profile_path, "CustomPluginVariables.JSON")
    copy(
        join(reciever_root_path, "templates", "CustomPluginVariables.JSON"),
        plugin_json_path,
    )
    # remove all plugins
    plugins_path = join(root_path, "server", "Bin64", "plugins")
    files = listdir(plugins_path)
    for plugin in files:
        full_plugin_path = join(plugins_path, plugin)
        if plugin.endswith(".dll"):
            unlink(full_plugin_path)
            logging.info(f"Removed {plugin} to restore vanilla state")
    with open(plugin_json_path, "w") as file_handle:
        logging.info(
            f"Overwriting CustomPluginVariables.JSON with an empty dict as there are no plugins at this moment"
        )
        file_handle.write("{}")
    logging.info("Wrote empty json into custom variables JSON from templates")
    with open(plugin_json_path, "r") as read_handle:
        content = loads(read_handle.read())
        if "plugins" in server_config["mod"]:
            plugins_to_add = server_config["mod"]["plugins"]
            for key, value in plugins_to_add.items():
                logging.info(
                    f"Adding plugin definition for {key} to CustomPluginVariables.JSON"
                )
                content[key] = value
            with open(plugin_json_path, "w") as write_handle:
                write_handle.write(dumps(content))

    overwrites = server_config["mod"]["server"]["overwrites"]
    for overwrite_file, overwrite_options in overwrites.items():
        full_path = join(profile_path, overwrite_file)
        parsed = load(open(full_path, "r"))
        for option, options in overwrite_options.items():
            for option_key, option_value in options.items():
                parsed[option][option_key] = option_value
        with open(full_path, "w") as overwrite_file_handle:
            overwrite_file_handle.write(dumps(parsed, indent=4, separators=(",", ": ")))

    web_ui_port = int(get_server_port(server_config))
    if web_ui_port == 5397:
        error_text = "The server setting WebUI port is still on the default value. Aborting deployment."
        logging.fatal(error_text)
        raise Exception(error_text)

    folder_paths = {
        join(user_data_path, "Replays"): [],
        join(user_data_path, "Log"): ["CBash", "Results", "Shaders"],
        join(server_root_path, "Packages"): ["Skins"],
        join(server_root_path, "appcache"): [],
        join(server_root_path, "steamapps"): [],
        join(user_data_path, "player", "Settings"): [],
    }

    collect_results_replays = (
        server_config["mod"]["collect_results_replays"]
        if "collect_results_replays" in server_config["mod"]
        else False
    )

    if collect_results_replays:
        logging.info("Making sure replay and results folder will persist")
        if not exists(join(server_root_path, "UserData", "Replays")):
            logging.info("Replays path was not yet existing, creating")
            mkdir(join(server_root_path, "UserData", "Replays"))
        replays_path = join(server_root_path, "UserData", "Replays", "apx-keep.txt")
        with open(replays_path, "w") as file:
            file.write("No delete, kthxbye")
        logging.info("Wrote lockfile into {}".format(replays_path))
        if not exists(join(server_root_path, "UserData", "Log")):
            logging.info("Logs path was not yet existing, creating")
            mkdir(join(server_root_path, "UserData", "Log"))
        results_path = join(server_root_path, "UserData", "Log", "apx-keep.txt")
        with open(results_path, "w") as file:
            file.write("No delete, kthxbye")
        logging.info("Wrote lockfile into {}".format(results_path))

    for folder_path, folders in folder_paths.items():
        if not exists(join(folder_path, "apx-keep.txt")):
            if exists(folder_path):
                logging.info("Removed tree in {}".format(folder_path))
                rmtree(folder_path)
            logging.info("Creating folder in {}".format(folder_path))
            mkdir(folder_path)
            if len(folders) > 0:
                for sub_folder in folders:
                    sub_folder_path = join(folder_path, sub_folder)
                    mkdir(sub_folder_path)
                    logging.info("Creating folder in {}".format(sub_folder_path))
        else:
            logging.info(
                "Ignoring the folder {} as it's marked as to be kept.".format(
                    folder_path
                )
            )

    # Overwrite installed an manifests
    template_copy_paths = {
        join(reciever_root_path, "templates", "Installed"): join(
            server_root_path, "Installed"
        ),
        join(reciever_root_path, "templates", "Manifests"): join(
            server_root_path, "Manifests"
        ),
    }

    for path, target_path in template_copy_paths.items():
        if exists(target_path):
            logging.info("Removing tree in {}".format(target_path))
            rmtree(target_path)

        logging.info("Applying template from {} to {}".format(path, target_path))
        copytree(path, target_path)
    do_update = server_config["mod"]["update_on_build"]
    if do_update:
        # Update the server itself using steam
        run_steamcmd(server_config, "update")
    else:
        logging.info("Skipping update of the server itself.")


def create_mas(
    server_config: dict, component_info: dict, add_version_suffix=False, is_vehicle=True
):
    root_path = server_config["server"]["root_path"]
    build_path = join(root_path, "build")
    name = component_info["name"]
    component_path = join(build_path, name)
    version = component_info["version"]
    if version == "latest" or version == "latest-even":
        # use the latest one or the lastest even version
        try:
            version = get_latest_version(
                join(
                    root_path,
                    "server",
                    "Installed",
                    "Vehicles" if is_vehicle else "Locations",
                    name,
                ),
                version == "latest",
            )
        except Exception as e:
            logging.error(e)
    if not add_version_suffix:
        target_path = join(build_path, name + ".mas")
    else:
        target_path = join(build_path, name + "_v" + version + VERSION_SUFFIX + ".mas")
    if exists(target_path):
        unlink(target_path)
        logging.info("Removed old mas file on {}".format(target_path))
    build_mas(server_config, component_path, target_path)


def build_mas(server_config: dict, source_path: str, target_path: str):
    """
    Add files from a given directory to a MAS file
    """
    root_path = server_config["server"]["root_path"]

    files_to_add = listdir(source_path)
    cmd_line = (
        f"{root_path}\\server\\Bin64\\ModMgr.exe -m"
        + target_path
        + " "
        + join(source_path, "*.*")
    )

    logging.info("Creating an mas file {}".format(cmd_line))
    build = subprocess.getstatusoutput(cmd_line)
    # keep casing
    lowercase_path = join(root_path, "build", target_path.lower())
    move(lowercase_path, target_path)
    return build[0] != 0


def find_location_properties(root_path: str, mod_name: str, desired_layout: str):
    default_wet_file = join(root_path, "reciever", "templates", "WEATHER.wet")
    if not exists(default_wet_file):
        raise Exception("The default weather template is missing")
    file_map = find_weather_and_gdb_files(root_path, mod_name)
    needles = {
        "TrackName": r"TrackName\s+=\s+([^\n]+)",
        "SettingsFolder": r"SettingsFolder\s+=\s+([^\n]+)",
    }
    property_map = {}
    for key, files in file_map.items():
        property_map[key] = {}
        gdb_matches = list(filter(lambda x: ".gdb" in x.lower(), files))
        wet_matches = list(filter(lambda x: ".wet" in x.lower(), files))
        if len(gdb_matches) != 1:
            raise Exception("No suitable GDB file found")

        gdb_file = join(key, gdb_matches[0])
        property_map[key]["GDB_SOURCE"] = gdb_file

        with open(gdb_file, "r") as file:
            content = file.read()
            for property, pattern in needles.items():
                matches = re.findall(pattern, content, re.MULTILINE)
                if matches is not None and len(matches) == 1:
                    property_map[key][property] = matches[0]
                    logging.info(
                        'Based on file situation, we identified "{}" as a property for {}.'.format(
                            matches[0], property
                        )
                    )

        if len(wet_matches) == 1:
            logging.info(
                "Found WET file. Using WET={}, WET_SOURCE={}".format(
                    wet_matches[0], join(key, wet_matches[0])
                )
            )
            property_map[key]["WET"] = wet_matches[0]
            property_map[key]["WET_SOURCE"] = join(key, wet_matches[0])

    for key, properties in property_map.items():
        if properties["TrackName"] == desired_layout:
            logging.info(
                "Using data {} for weather injection.".format(properties["TrackName"])
            )
            # if there is no weather file -> create
            if "WET" not in properties:
                # create wet source
                # We assume that the WET file and the GDB file share the same name
                wet_filename = (
                    basename(property_map[key]["GDB_SOURCE"])
                    .replace(".gdb", ".WET")
                    .replace(".GDB", ".WET")
                )
                artifical_wet_file_path = join(key, wet_filename)

                # Copy template file
                copy(default_wet_file, artifical_wet_file_path)
                properties["WET"] = wet_filename
                properties["WET_SOURCE"] = artifical_wet_file_path

                logging.info(
                    "No WET file found. Creating one for WET={}, WET_SOURCE={}".format(
                        wet_filename, artifical_wet_file_path
                    )
                )
            return properties
    logging.warn(
        "There is no suitable GDB content found. The desired layout was {}".format(
            desired_layout
        )
    )
    return None


def find_weather_and_gdb_files(root_path: str, mod_name):
    modmgr_path = join(root_path, "server", "Bin64\\ModMgr.exe")
    mod_root_path = join(root_path, "server", "Installed", "locations", mod_name)
    mod_versions = listdir(mod_root_path)
    server_root_path = join(root_path, "server")
    file_map = {}
    for version in mod_versions:
        mod_version_path = join(mod_root_path, version)
        files = listdir(mod_version_path)
        for file in files:
            if ".mas" in file:
                full_mas_path = join(mod_version_path, file)
                extraction_path = join(root_path, "build", file + "_extraction")
                if not exists(extraction_path):
                    mkdir(extraction_path)
                cmd_line_gdb = '{} -x{} "*.gdb" -o{}'.format(
                    modmgr_path, full_mas_path, extraction_path
                )
                cmd_line_wet = '{} -x{} "*.wet" -o{}'.format(
                    modmgr_path, full_mas_path, extraction_path
                )
                cmd_line_grip = '{} -x{} "*.rrbin" -o{}'.format(
                    modmgr_path, full_mas_path, extraction_path
                )
                subprocess.check_output(cmd_line_gdb)
                subprocess.check_output(cmd_line_wet)
                subprocess.check_output(cmd_line_grip)
                files_collected = listdir(extraction_path)
                grip_files = list(
                    filter(lambda x: ".rrbin" in x.lower(), files_collected)
                )
                if len(grip_files) > 0:
                    logging.info(
                        "We managed to extract following grip files from the MAS file {}: {}".format(
                            file,
                            ",".join(grip_files),
                        )
                    )
                if len(files_collected) == 0:
                    rmtree(extraction_path)
                else:
                    file_map[extraction_path] = files_collected

    return file_map
