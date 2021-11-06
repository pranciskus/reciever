from os.path import join, exists, basename, pathsep, dirname
from os import listdir, mkdir, getenv, unlink, stat
from shutil import copy, rmtree, copytree, move
from rf2.steam import run_steamcmd, install_mod, get_steamcmd_path, find_source_path
import subprocess
from time import sleep
from json import loads, dumps, load, dump
import re
from distutils.version import LooseVersion
import logging
from rf2.steam import get_entries_from_mod, extract_veh_files, get_layouts
from rf2.util import get_server_port
from datetime import datetime
import io
import zipfile
from requests import get
import hashlib
import tempfile

VERSION_SUFFIX = ".9apx"
WEATHERCLIENT_URL = "https://forum.studio-397.com/index.php?attachments/rf2weatherpluginv1-14a-zip.40498/"


def add_weather_client(root_path, api_type, key, uid, temp_offset, reinstall=False):
    weather_path = join(root_path, "weatherclient")
    logging.info(
        f"Adding weather client in directory {weather_path}. API will be {api_type}"
    )
    if reinstall:
        rmtree(weather_path)
    if not exists(weather_path):
        # install the weather client structure
        mkdir(weather_path)
        r = get(WEATHERCLIENT_URL)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(weather_path)
        # create wanted folder structure
        sub_folder = listdir(weather_path)[0]
        files_extracted = listdir(join(weather_path, sub_folder))
        for file in files_extracted:
            old_path = join(weather_path, sub_folder, file)
            new_path = join(weather_path, file)
            move(old_path, new_path)
        rmtree(join(weather_path, sub_folder))
    # inject config
    type_map = {
        "OpenWeatherMap": "OWApi",
        "DarkSky": "DSApi",
        "ClimaCell": "CCApi",
        "ClimaCell_V4": "CCApiV4",
    }
    template_file = join(root_path, "reciever", "templates", "rf2WeatherClient.xml")
    with open(template_file, "r") as read_handle:
        content = read_handle.read()
        content = content.replace("$API$", api_type)
        content = content.replace("$TYPE$", type_map[api_type])
        content = content.replace("$KEY$", key)
        content = content.replace("$UID$", str(uid))
        content = content.replace("$TEMPOFFSET$", str(temp_offset))
        target_path = join(weather_path, "rf2WeatherClient.xml")
        with open(target_path, "w") as write_handle:
            write_handle.write(content)
        logging.info(
            f"Wrote {target_path} weather client file. We will have a temperature offset of {temp_offset}"
        )
    # add the weather DLL
    plugin_src_path = join(weather_path, "rf2WeatherPlugin.dll")
    plugin_target_path = join(
        root_path, "server", "Bin64", "Plugins", "rf2WeatherPlugin.dll"
    )
    copy(plugin_src_path, plugin_target_path)
    logging.info(f"Added weather plugin file to {plugin_target_path}")
    # add the dll to the custom variables json file
    custom_variables_file = join(
        root_path, "server", "userData", "player", "CustomPluginVariables.JSON"
    )
    json = load(open(custom_variables_file, "r"))
    json["rf2WeatherPlugin.dll"] = {" Enabled": 1, "LOG": 0, "UID": int(uid)}
    new_content = dumps(json)
    with open(custom_variables_file, "w") as file:
        file.write(new_content)
    logging.info(f"Added weather plugin file to {custom_variables_file}")


def generate_veh_templates(target_path: str, veh_templates: list, component_info: dict):
    if len(veh_templates) == 0:
        logging.exception(
            f"There is no suitable VEH file to use inside of {veh_templates}"
        )
        raise Exception(
            f"There is no suitable VEH file to use inside of {veh_templates}"
        )

    short_name = component_info["component"]["short"]
    entries = component_info["entries"]
    for entry in entries:

        parts = entry.split("#")
        name = parts[0]
        number_parts = parts[1].split(":")
        number = number_parts[0]
        pit_group = number_parts[1]
        # check if overwrites might be there
        overwrites = (
            component_info["entries_overwrites"][number]
            if number in component_info["entries_overwrites"]
            else None
        )

        veh_template = veh_templates[0]  # later with filter
        if overwrites and "BaseClass" in overwrites:
            base_class = overwrites["BaseClass"]
            # search for a suitable base VEH file
            matched = False
            for template in veh_templates:
                if matched:
                    break
                with open(template, "r") as template_handle:
                    content = template_handle.readlines()
                    for line in content:
                        if (
                            "classes" in line.lower()
                            and overwrites["BaseClass"].lower() in line.lower()
                        ):
                            line_log = line.replace("\n", "")
                            logging.info(
                                f'We will choose the VEH file as a template: {template} as it suits the BaseClass string "{base_class}": {line_log}'
                            )
                            matched = True
                            veh_template = template
                            break

        else:
            logging.info(
                f"We will choose the first VEH file as a template: {veh_template}"
            )
        with open(veh_template, "r") as veh_template_handle:
            content = veh_template_handle.read()
            logging.info(f"Creating VEH file for {entry}")
            # ER_AlpineSeries_rF2#52:1

            description = f"{name}#{number}"
            replacementMap = {
                "DefaultLivery": short_name + f"_{number}.dds",
                "Number": f"{number}",
                "Team": f"{name}",
                "Description": f"{description}",
                "FullTeamName": f"{description}",
                "PitGroup": f"Group{pit_group}",
            }
            templateLines = content.split("\n")
            newLines = []
            for line in templateLines:
                hadReplacement = False
                for key, value in replacementMap.items():
                    pattern = r"(" + key + '\s{0,}=\s{0,}"?([^"^\n^\r]+)"?)'
                    matches = re.match(pattern, line, re.MULTILINE)
                    replacement = "{}={}\n".format(key, value)
                    if matches:
                        fullMatch = matches.groups(0)[0]
                        if '"' in fullMatch:
                            replacement = '{}="{}"\n'.format(key, value)

                        newLines.append(replacement)
                        hadReplacement = True
                if not hadReplacement:
                    newLines.append(line)
            # write the new VEH file
            if len(newLines) > 0:
                result = "\n".join(newLines)
                if overwrites:
                    print(
                        "Found overwrites for VEH template for entry {}".format(number)
                    )
                    template_lines = result.split("\n")
                    template_lines_with_overwrites = []
                    for line in template_lines:
                        line_to_add = None
                        for key, value in overwrites.items():
                            pattern = r"(" + key + '\s{0,}=\s{0,}"?([^"^\n^\r]{0,})"?)'
                            matches = re.match(pattern, line)
                            use_quotes = '"' in line
                            if matches:
                                line_to_add = "{}={}\n".format(
                                    key,
                                    value if not use_quotes else '"{}"'.format(value),
                                )
                                logging.info(
                                    "Using value {} (in quotes: {}) for key {} of entry {}".format(
                                        value,
                                        use_quotes,
                                        key,
                                        number,
                                    )
                                )
                                break
                        if line_to_add:
                            template_lines_with_overwrites.append(line_to_add)
                        else:
                            template_lines_with_overwrites.append(line + "\n")
                        result = "".join(template_lines_with_overwrites)
                full_path = join(target_path, short_name + "_" + number + ".veh")
                with open(full_path, "w") as file:
                    file.write(result)


def get_mod_encryption(root_path: str, mod_name: str, type: str) -> dict:
    content_needles = {
        "Vehicles": ["*.json", "*.ini", "*.veh"],
        "Locations": ["*.gdb", "*.ini", "*.wet", "*.tdf", "*.json"],
    }
    component_path = join(root_path, "server", "Installed", type, mod_name)
    component_versions = listdir(component_path)
    official_mods_result = {}
    for version in component_versions:
        mod_mgr = join(root_path, "server", "Bin64", "ModMgr.exe")
        version_path = join(component_path, version)
        version_files = listdir(version_path)
        for version_file in version_files:
            if ".mas" in version_file.lower():  # attempt to list mas file content
                with tempfile.TemporaryDirectory() as tmpdirname:
                    for needle in content_needles["Vehicles"]:
                        full_version_file_path = join(version_path, version_file)
                        cmd_line = '{} -x"{}" "{}" -o{}'.format(
                            mod_mgr, full_version_file_path, needle, tmpdirname
                        )
                        subprocess.getstatusoutput(cmd_line)

                    files = listdir(tmpdirname)
                    if version not in official_mods_result:
                        official_mods_result[version] = {}
                    official_mods_result[version][version_file] = len(files) != 0
                    if len(files) == 0:
                        logging.warn(
                            f"From the file {version_file} no files could be extracted"
                        )
    logging.info(f"The mod {mod_name} has following structure")
    results = {}
    for version, files in official_mods_result.items():
        has_open_mod = True
        for file_name, open_flag in files.items():
            if not open_flag:
                logging.info(
                    f"Version {version} has at least one encrypted mod: {file_name}"
                )
                has_open_mod = False
                break
        if has_open_mod:
            logging.info(f"Version {version} has at least one open mod")
        results[version] = has_open_mod
    return results


def is_official_mod(
    root_path: str,
    mod_name: str,
    type: str,
    force_version_ignore_encryption: bool = False,
) -> bool:
    results = get_mod_encryption(root_path, mod_name, type)
    has_base_version = len(results) == 2
    if not has_base_version:
        logging.info(
            "The mod has only one version, skipping check for official mod structure"
        )
        return False
    if not force_version_ignore_encryption:
        if not list(results.values())[0] and list(results.values())[1]:
            logging.info(
                "The mod has multiple versions, the first one is encrypted, the second is not. This is considered an official mod scheme."
            )
            return True
    else:
        if has_base_version:
            logging.info(
                "The mod has two versions, skipping check encryption as user requested"
            )
            return True
    logging.info(
        "The mod has multiple versions, but the encryption is not as expected. Might be third party."
    )
    return False


def deploy_server(
    server_config: dict, rfm_contents: str, grip_data, onStateChange, status_hooks
) -> bool:
    root_path = server_config["server"]["root_path"]
    log_path = join(root_path, "reciever.log")
    with open(log_path, "w"):
        pass
    logging.info("Starting server deploy")
    vehicles = server_config["mod"]["cars"]
    tracks = server_config["mod"]["track"]
    suffix = server_config["mod"]["suffix"]
    ignore_fingerprints = (
        "ignore_fingerprints" in server_config["mod"]
        and server_config["mod"]["ignore_fingerprints"]
    )
    force_versions = (
        "force_versions" in server_config["mod"]
        and server_config["mod"]["force_versions"] > 0
    )
    force_version_ignore_encryption = (
        "force_versions" in server_config["mod"]
        and server_config["mod"]["force_versions"] == 2
    )
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

    event_config = server_config["mod"]
    all_steam_ids = []
    for key, vehicle in vehicles.items():
        id = vehicle["component"]["steam_id"]
        base_id = vehicle["component"]["base_steam_id"]
        if ":" in str(id):  # the workshop_id is prefixed
            raw_id = id
            id = str(id).split(":")[0]

        if base_id != 0 and base_id not in all_steam_ids and "-" not in str(base_id):
            all_steam_ids.append(base_id)
        if id not in all_steam_ids and "-" not in str(id):
            all_steam_ids.append(id)

    for workshop_id, track in tracks.items():
        id = track["component"]["steam_id"]
        base_id = track["component"]["base_steam_id"]
        if ":" in str(id):  # the workshop_id is prefixed
            raw_id = id
            id = str(id).split(":")[0]

        if base_id != 0 and base_id not in all_steam_ids and "-" not in str(base_id):
            all_steam_ids.append(base_id)
        if id not in all_steam_ids and "-" not in str(id):
            all_steam_ids.append(id)

    logging.info(
        "We seen {} different steam id's in this deployment.".format(len(all_steam_ids))
    )

    for id in all_steam_ids:
        if id > 0:
            logging.info(
                f"Installing workshop item {id} before mod installation to make sure fingerprints can be generated"
            )
            run_steamcmd(server_config, "add", id)

    # generate fingerprints

    apx_origin_path = join(root_path, "reciever", "mod.apx.json")
    path = join(root_path, "reciever", "mod.json")
    # for this fingerprint, we will use the path (new file, but without version numbers)
    if not ignore_fingerprints:
        fingerprints = get_fingerprints(event_config, server_config, root_path)

        fingerprint_path = join(root_path, "reciever", "fingerprint.json")
        if exists(fingerprint_path):
            old_file = load(open(fingerprint_path, "r"))
            if old_file == fingerprints:
                logging.warning(
                    f"The fingerprints are equal. Triggering the deployment to fail hard. Old fingerprints: {old_file}, new fingerprints after running steam: {fingerprints}"
                )
                raise Exception("No mod files changed, aborted deployment.")
            else:
                logging.info(
                    "Continuing as planned. Mod content and/ or updates changed."
                )
    else:
        logging.info("User choosed to ignore fingerprints.")

    # removal of unused steam mods
    if (
        "remove_unused_mods" in server_config["mod"]
        and server_config["mod"]["remove_unused_mods"]
    ):
        steam_root_path = join(
            root_path, "steamcmd", "steamapps", "workshop", "content", "365960"
        )
        all_steam_downloads = listdir(steam_root_path)
        logging.info(
            "There are currently {} steam workshop items downloaded".format(
                len(all_steam_downloads)
            )
        )
        for steam_id in all_steam_downloads:
            full_item_path = join(steam_root_path, steam_id)
            if steam_id not in all_steam_ids:
                logging.info(
                    f"We will remove the path {full_item_path} to save storage."
                )
                rmtree(full_item_path)
                logging.info(f"Removed {full_item_path} to save storage.")
            else:
                logging.info(
                    f"We will NOT remove the path {full_item_path} as it's part of this deployment"
                )
    else:
        logging.info("We will not attempt to cleanup steamcmd downloads.")
    onStateChange("Restoring vanilla state and doing Steam update", None, status_hooks)
    restore_vanilla(server_config)
    # build vehicle mods
    for key, vehicle in vehicles.items():
        workshop_id = str(vehicle["component"]["steam_id"])
        if ":" in workshop_id:  # the workshop_id is prefixed
            raw_id = workshop_id
            workshop_id = workshop_id.split(":")[0]
            logging.info(
                f"The provided workshop id {raw_id} is suffixed. Removed suffix. Using {workshop_id} as the ID"
            )
        if int(vehicle["component"]["base_steam_id"]) > 0:
            logging.info(
                f"The item is based on another item. Demanding installation of base mod."
            )
            onStateChange(
                "Installing base workshop item",
                vehicle["component"]["base_steam_id"],
                status_hooks,
            )
            # run_steamcmd(server_config, "add", vehicle["component"]["base_steam_id"])
            install_mod(server_config, int(vehicle["component"]["base_steam_id"]), None)
        if int(workshop_id) > 0:
            # if the workshop id is present, attempt install
            onStateChange("Installing workshop item", workshop_id, status_hooks)
            # run_steamcmd(server_config, "add", workshop_id)
        component_info = vehicle["component"]
        update = component_info["update"]
        official = component_info["official"]
        install_mod(server_config, int(workshop_id), component_info["name"])
        official_check = force_versions and is_official_mod(
            root_path,
            component_info["name"],
            "Vehicles",
            force_version_ignore_encryption,
        )
        if not official and official_check:
            logging.warning(
                "The check for official versioning scheme for mod {} showed that this might be official content, but the user did not flag it as such.".format(
                    component_info["name"]
                )
            )
            official = True
            logging.warning(
                "Flagged {} as official as force_versions is set.".format(
                    component_info["name"]
                )
            )
        if update and official:
            logging.info(
                "Requested update on top of component {} which is marked as official content. Selecting latest-even version".format(
                    component_info["name"]
                )
            )
            component_info["version"] = "latest-even"
        onStateChange("Installing vehicle", component_info["name"], status_hooks)

        if component_info["update"]:

            version = get_latest_version(
                join(
                    root_path, "server", "Installed", "Vehicles", component_info["name"]
                ),
                component_info["version"] == "latest",
            )
            files = extract_veh_files(root_path, component_info["name"], version)
            build_path = join(root_path, "build")
            component_path = join(build_path, component_info["name"])
            files_in_component_path = listdir(component_path)
            if (
                len(list(filter(lambda x: x.endswith(".veh"), files_in_component_path)))
                == 0
            ):
                logging.info(
                    f"We did not see a single VEH file inside of {component_path}. We will generate them now."
                )
                generate_veh_templates(component_path, files, vehicle)
            else:
                logging.info(
                    f"Skipping generation of additional VEh files as there are veh files inside of {component_path}."
                )
            create_mas(server_config, component_info, True)
            build_cmp_mod(server_config, component_info, "Vehicles", True)
            onStateChange(
                "Creating cmp mod for vehicle", component_info["name"], status_hooks
            )

    for key, track in tracks.items():
        workshop_id = str(track["component"]["steam_id"])
        if int(track["component"]["base_steam_id"]) > 0:
            logging.info(
                f"The item is based on another item. Demanding installation of base mod."
            )
            onStateChange(
                "Installing base workshop item",
                track["component"]["base_steam_id"],
                status_hooks,
            )
            # run_steamcmd(server_config, "add", track["component"]["base_steam_id"])
            install_mod(server_config, int(track["component"]["base_steam_id"]), None)
        if int(workshop_id) > 0:
            # if the workshop id is present, attempt install
            onStateChange("Installing workshop item", workshop_id, status_hooks)
            # run_steamcmd(server_config, "add", workshop_id)

        onStateChange("Installing track", track["component"]["name"], status_hooks)

        install_mod(server_config, int(workshop_id), track["component"]["name"])
        official_check = force_versions and is_official_mod(
            root_path,
            track["component"]["name"],
            "Locations",
            force_version_ignore_encryption,
        )
        official = track["component"]["official"]
        if not official and official_check:
            logging.warning(
                "The check for official versioning scheme for mod {} showed that this might be official content, but the user did not flag it as such.".format(
                    track["component"]["name"]
                )
            )
            official = True
            logging.warning(
                "Flagged {} as official as force_versions is set.".format(
                    track["component"]["name"]
                )
            )
        component_info = track["component"]
        update = component_info["update"]

        if update and official:
            logging.info(
                "Requested update on top of component {} which is marked as official content. Selecting latest-even version".format(
                    component_info["name"]
                )
            )
            component_info["version"] = "latest-even"

        if component_info["update"]:
            build_path = join(root_path, "build")
            component_path = join(build_path, component_info["name"])
            files_in_component_path = listdir(component_path)
            if (
                len(
                    list(
                        filter(
                            lambda x: x.lower().endswith(".mas"),
                            files_in_component_path,
                        )
                    )
                )
                > 0
            ):
                logging.info(
                    "The component build path contains prebuild MAS files. We will pick them up instead of generating own ones"
                )
                provided_mas_paths = list(
                    filter(
                        lambda x: x.lower().endswith(".mas"), files_in_component_path
                    )
                )
                modmgr_path = join(root_path, "server", "Bin64\\ModMgr.exe")
                for mas_file in provided_mas_paths:
                    full_mas_path = join(component_path, mas_file)
                    # extract the mas file
                    logging.info(
                        f"Attempting to extract files of {full_mas_path} into {component_path}"
                    )
                    cmd_line = '{} -x"{}" "*.*" -o{}'.format(
                        modmgr_path, full_mas_path, component_path
                    )
                    subprocess.check_output(cmd_line)
                    logging.info(
                        "Found {} files in {}".format(
                            len(listdir(component_path)) - 1, component_path
                        )
                    )
                    # remove the mas file as it serves no purpose anymore
                    unlink(full_mas_path)
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
    build_mod(server_config, vehicles, tracks, mod_info, rfm_contents)

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
    copy(path, apx_origin_path)
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

    if (
        "skip_all_session_unless_configured" in event_config
        and event_config["skip_all_session_unless_configured"]
    ):
        logging.info(
            "Event has option set to skip all sessions unless the ones configured."
        )
        player_json["Race Conditions"]["Run Warmup"] = False
        for i in range(1, 5):
            player_json["Race Conditions"]["Run Practice{}".format(i)] = False
        for area in ["CHAMP", "CURNT", "GPRIX", "MULTI", "RPLAY"]:
            player_json["Race Conditions"][f"{area} Num Qual Sessions"] = 0
            player_json["Race Conditions"][f"{area} Num Race Sessions"] = 0

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
            player_json["Race Conditions"]["RealRoadTimeScalePractice"] = session[
                "grip_scale"
            ]
            player_json["Race Conditions"]["Run Practice1"] = True
            multiplayer_json["Multiplayer Server Options"]["Practice 1 Time"] = length

        if type == "Q1":
            if time_after_midnight:
                player_json["Race Conditions"][
                    "QualifyingStartingTime"
                ] = time_after_midnight
            player_json["Race Conditions"]["RealRoadTimeScaleQualifying"] = session[
                "grip_scale"
            ]
            for area in ["CHAMP", "CURNT", "GPRIX", "MULTI", "RPLAY"]:
                player_json["Race Conditions"][f"{area} Num Qual Sessions"] = 1
            if laps == 0:
                multiplayer_json["Multiplayer Server Options"]["Qualifying Laps"] = 255
            else:
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
            player_json["Race Conditions"]["RealRoadTimeScaleRace"] = session[
                "grip_scale"
            ]

            for area in ["CHAMP", "CURNT", "GPRIX", "MULTI", "RPLAY"]:
                player_json["Race Conditions"][f"{area} Num Race Sessions"] = 1
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

    if (
        "race_finish_criteria" in event_config
        and event_config["race_finish_criteria"] is not None
    ):
        for area in ["CHAMP", "CURNT", "GPRIX", "MULTI", "RPLAY"]:
            player_json["Game Options"][f"{area} Race Finish Criteria"] = event_config[
                "race_finish_criteria"
            ]
        logging.info(
            "We will use a user defined race finish criteria: "
            + str(event_config["race_finish_criteria"])
        )
    onStateChange("Updating player.json", None, status_hooks)
    with open(player_json_path, "w") as file:
        logging.info("Updating player.json to represent session dimensions")
        dump(player_json, file, indent=4, separators=(",", ": "))

    onStateChange("Updating multiplayer.json", None, status_hooks)
    with open(multiplayer_json_path, "w") as file:
        logging.info("Updating multiplayer.json to represent session dimensions")
        dump(multiplayer_json, file, indent=4, separators=(",", ": "))

    logging.info("Finished server deploy")

    # create fingerprint file to allow conditional server updates
    fingerprint_path = join(root_path, "reciever", "fingerprint.json")
    logging.info(f"Create modpack fingerprints file {fingerprint_path}")
    fingerprint_file = get_fingerprints(event_config, server_config, root_path)
    with open(fingerprint_path, "w") as file:
        file.write(dumps(fingerprint_file))
    logging.info(f"Finished fingerprinting")
    onStateChange("Deployment finished successfully", None, status_hooks)
    return True


def get_fingerprints(event_config: dict, server_config: dict, root_path: str):
    fingerprint_file = {}
    for _, vehicle in event_config["cars"].items():
        steam_id = vehicle["component"]["steam_id"]
        base_steam_id = vehicle["component"]["base_steam_id"]
        component_name = vehicle["component"]["name"]
        # find the mod file of this mod
        base_mod_fingerprints = None
        if base_steam_id != 0:
            base_mod_fingerprints = get_mod_fingerprints(
                server_config, base_steam_id, None
            )  # a base mod cannot be a file based item
            fingerprint_file[str(base_steam_id)] = base_mod_fingerprints
        mod_fingerprints = get_mod_fingerprints(server_config, steam_id, component_name)
        fingerprint_file[str(steam_id)] = mod_fingerprints

        # check track updates
        if vehicle["component"]["update"]:
            build_path = join(root_path, "build", component_name)
            if exists(build_path):
                fingerprint_file[f"{steam_id}_update"] = folder_fingerprints(build_path)

    for _, track in event_config["track"].items():
        steam_id = track["component"]["steam_id"]
        base_steam_id = track["component"]["base_steam_id"]
        component_name = track["component"]["name"]
        # find the mod file of this mod
        base_mod_fingerprints = None
        if base_steam_id != 0:
            base_mod_fingerprints = get_mod_fingerprints(
                server_config, base_steam_id, None
            )  # a base mod cannot be a file based item
            fingerprint_file[str(base_steam_id)] = base_mod_fingerprints
        mod_fingerprints = get_mod_fingerprints(server_config, steam_id, component_name)
        fingerprint_file[str(steam_id)] = mod_fingerprints

        # check track updates
        if track["component"]["update"]:
            build_path = join(root_path, "build", component_name)
            if exists(build_path):
                fingerprint_file[f"{steam_id}_update"] = folder_fingerprints(build_path)
    return fingerprint_file


def get_mod_fingerprints(server_config: dict, steam_id: int, component_name: str):
    steam_root = get_steamcmd_path(server_config)
    source_path = (
        join(steam_root, "steamapps\\workshop\\content\\365960\\", str(steam_id))
        if steam_id > 0
        else find_source_path(root_path, component_name)
    )
    fingerprints = folder_fingerprints(source_path)
    return fingerprints


def folder_fingerprints(source_path: str):
    mod_files = listdir(source_path)
    fingerprints = {}
    for mod_file in mod_files:
        if ".veh" not in mod_file:  # we are ignoring generated veh files here.
            full_path = join(source_path, mod_file)
            fingerprints[mod_file] = checksum(full_path)
    return fingerprints


def checksum(filename):
    h = hashlib.sha1()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, "rb", buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()


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
    if not exists(condition_files_root_path):
        mkdir(condition_files_root_path)
    weather_file_parent = join(condition_files_root_path, properties["SettingsFolder"])
    if not exists(weather_file_parent):
        mkdir(weather_file_parent)
    weather_file_path = join(
        weather_file_parent, properties["WET"].replace(".WET", "s.WET")
    )
    weather_template = (
        weather_file_path if exists(weather_file_path) else properties["WET_SOURCE"]
    )
    logging.info(f"The file {weather_template} is used as a template.")
    extraction_path = dirname(properties["GDB_SOURCE"])
    extraction_path_files = listdir(extraction_path)
    extraction_path_files.sort()
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
            if (
                grip_needle
                and grip_needle.lower() == "green"
                or grip_needle
                and grip_needle.lower() == "natural"
            ):
                logging.info(
                    f"Session {type} will be using {grip_needle} as a ingame start point."
                )
                content = re.sub(
                    r"RealRoad{}=\".+\"".format(type),
                    'RealRoad{}="{}"'.format(type, grip_needle.lower()),
                    content,
                )
            else:
                if grip_needle and grip_needle.lower() == "autosave":
                    autosave_path = join(weather_file_parent, "AutoSave.rrbin")
                    if exists(autosave_path):
                        logging.info(
                            f"The grip needle for {type} demands an autosave. The file exists and will be used."
                        )
                        content = re.sub(
                            r"RealRoad{}=\".+\"".format(type),
                            'RealRoad{}="user:AutoSave.rrbin"'.format(type),
                            content,
                        )
                    else:
                        logging.info(
                            f"There is no autosave file found for {type} at the moment. Start the server once to make it available and deploy again."
                        )
                if grip_needle and grip_needle.lower() != "autosave":
                    logging.info(
                        f"Attempting to find a grip file for session {type} by needle {grip_needle}"
                    )
                    found_gripfile = False
                    found_gripfile_name = None
                    for file in extraction_path_files:
                        lower_file = file.lower()
                        if ".rrbin" in lower_file and grip_needle in lower_file:
                            logging.info(
                                "Session {} will use preset grip file {}".format(
                                    type, file
                                )
                            )
                            content = re.sub(
                                r"RealRoad{}=\".+\"".format(type),
                                'RealRoad{}="preset:{}"'.format(type, file),
                                content,
                            )
                            found_gripfile = True
                            found_gripfile_name = file
                        try:
                            if re.match(grip_needle, lower_file):
                                content = re.sub(
                                    r"RealRoad{}=\".+\"".format(type),
                                    'RealRoad{}="preset:{}"'.format(type, file),
                                    content,
                                )
                                logging.info(
                                    "Session {} will use preset grip file {}, matched by regex {}".format(
                                        type, file, grip_needle
                                    )
                                )
                                found_gripfile = True
                                found_gripfile_name = file
                        except:
                            logging.warning(
                                "Applying an regex for {} did not result in success".format(
                                    grip_needle
                                )
                            )
                    if found_gripfile and "autosave" in grip_needle.lower():
                        autosave_path = join(weather_file_parent, "AutoSave.rrbin")
                        if not exists(autosave_path) and found_gripfile_name:
                            logging.info(
                                "Session {} will use a preset grip file {} which will be used as future auto save file.".format(
                                    type, found_gripfile_name
                                )
                            )
                            source_path = join(extraction_path, found_gripfile_name)
                            copy(source_path, autosave_path)
                            logging.info(f"Copied {source_path} to {autosave_path}")
                        else:
                            logging.info(
                                "Session {} want's a preset become a auto save file, but the file is already existing. Doing nothing.".format(
                                    type, found_gripfile_name
                                )
                            )
                        content = re.sub(
                            r"RealRoad{}=\".+\"".format(type),
                            'RealRoad{}="user:AutoSave.rrbin"'.format(type),
                            content,
                        )

                else:
                    logging.info(
                        "Session {} will not use preset grip files".format(type)
                    )

        logging.info(f"Writing grip additions into file {weather_file_path}")
        with open(weather_file_path, "w") as weather_write_handle:
            weather_write_handle.write(content)
    return True


def get_latest_version(root_path: str, latest=True) -> str:
    versions = listdir(root_path)
    if len(versions) == 1:
        logging.info(
            "We don't need to sort here as only one version ({}) for {} is available. Falling back.".format(
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
    server_config: dict, vehicles: dict, tracks: dict, mod_info: dict, rfm_contents: str
):
    root_path = server_config["server"]["root_path"]
    data = ""
    with open("templates/pkginfo.dat") as f:
        data = f.read()

    veh_contents = ""
    track_contents = ""
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

    for _, track in tracks.items():
        component = track["component"]
        name = component["name"]
        version = component["version"]

        # version == latest -> choose "latest" available version
        if version == "latest" or version == "latest-even":
            # use the latest one or the lastest even version
            version = get_latest_version(
                join(root_path, "server", "Installed", "Locations", name),
                version == "latest",
            )
            logging.info(f"Using {version} as mod version for item {name}")
            print("Using", version, "as mod version for item", name)

        line = 'Track="' + name + " v" + version + ',0" '
        layouts = get_layouts(root_path, name, version)
        layouts_string = ""
        found_track = False
        for layout in layouts:
            possible_values = layout.keys()
            for possible_value in possible_values:
                if layout[possible_value] is not None:
                    enable_flag = (
                        "1" if track["layout"] == layout[possible_value] else 0
                    )
                    logging.info(f"Found data {possible_value}, {layout}, {track}")
                    logging.info(
                        "Checking if layout key "
                        + possible_value
                        + " with value "
                        + layout[possible_value]
                        + " can match "
                        + track["layout"]
                        + f": {enable_flag}"
                    )
                    if enable_flag == "1":
                        found_track = True
                        break
                else:
                    logging.info(f"Skipping key {possible_value} as the value is None")
            if found_track:
                layout_text = layout["EventName"].replace('"', '\\"')
                layouts_string = layouts_string + '"' + f'{layout_text},{enable_flag}"'
                break
        if found_track:
            logging.info(
                "We found the track desired, all other track layouts are set to be disabled. Track desired: "
                + track["layout"]
            )
        else:
            for layout in layouts:
                layout_text = layout["EventName"].replace('"', '\\"')
                layouts_string = layouts_string + '"' + f'{layout_text},1"'
            desired_layout = track["layout"]
            logging.info(
                f"We don't found the desired layout in the gdb layout list. Enabling all tracks. Desired layout name is {desired_layout}, track list is {layouts}"
            )

        line = line + layouts_string
        track_contents = track_contents + line + "\n"

    replacements = {
        "mod_name": mod_info["name"],
        "mod_version": mod_info["version"],
        "location": join(root_path, "server", "Packages", mod_info["name"] + ".rfmod"),
        "track_mods_count": str(len(tracks)),
        "veh_mods_count": str(len(vehicles)),
        "track_mod_contents": track_contents,
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
        join(user_data_path, "Log"): ["Results"],
        join(server_root_path, "Packages"): ["Skins"],
        join(server_root_path, "appcache"): [],
        join(server_root_path, "steamapps"): [],
    }

    if (
        "remove_settings" in server_config["mod"]
        and server_config["mod"]["remove_settings"] == True
    ):
        folder_paths[join(user_data_path, "player", "Settings")] = []
        logging.info(
            "User choosed to remove settings folders. Will be included in deletion"
        )
    else:
        logging.info("User choosed to persist settings. Will not be changed.")

    if (
        "remove_cbash_shaders" in server_config["mod"]
        and server_config["mod"]["remove_cbash_shaders"] == True
    ):
        folder_paths[join(user_data_path, "Log")] = ["CBash", "Results", "Shaders"]
        logging.info(
            "User choosed to remove CBash and shader folders. Will be included in deletion"
        )
    else:
        logging.info("User choosed to persist CBash and folders. Will not be changed.")

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

def update_server_only(server_config: dict):
    run_steamcmd(server_config, "update")

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
        "EventName": r"EventName\s+=\s+([^\n]+)",
        "VenueName": r"VenueName\s+=\s+([^\n]+)",
        "TrackNameShort": r"TrackNameShort\s+=\s+([^\n]+)",
        "SettingsFolder": r"SettingsFolder\s+=\s+([^\n^\/]+)",
    }
    property_map = {}
    for key, files in file_map.items():
        property_map[key] = {}
        gdb_matches = list(filter(lambda x: ".gdb" in x.lower(), files))
        wet_matches = list(filter(lambda x: ".wet" in x.lower(), files))
        if len(gdb_matches) != 1:
            logging.error("We found {} files for {}".format(len(gdb_matches), key))
            raise Exception("No suitable GDB file found")

        gdb_file = join(key, gdb_matches[0])
        property_map[key]["GDB_SOURCE"] = gdb_file

        with open(gdb_file, "r") as file:
            content = file.read()
            for property, pattern in needles.items():
                matches = re.findall(pattern, content, re.MULTILINE)
                if matches is not None and len(matches) == 1:
                    property_map[key][property] = matches[0].strip()
                    logging.info(
                        'Based on file situation, we identified "{}" as a property for {}.'.format(
                            property_map[key][property], property
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
        haystack = []
        for needle in ["TrackNameShort", "TrackName", "EventName", "VenueName"]:
            if needle in properties:
                haystack.append(properties[needle])
        if desired_layout in haystack:
            desired_layout = properties["EventName"]
            logging.info(
                "Setting the desired layout to {} to make sure the game works with it.".format(
                    desired_layout
                )
            )
            logging.info("Using data {} for weather injection.".format(desired_layout))
            # write a marker to remember the GDB name
            # ASSUMPTION = GDB FILENAME IN UPPERCASE == CALLVOTE NAME
            gdb_name_path = join(root_path, "reciever", "gdbname.txt")
            gdb_name = basename(properties["GDB_SOURCE"]).upper().replace(".GDB", "")
            logging.info(
                "Writing marker {} with content {} to remember GDB name".format(
                    gdb_name_path, gdb_name
                )
            )
            with open(gdb_name_path, "w") as file:
                file.write(gdb_name)
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
            if ".mas" in file.lower():
                full_mas_path = join(mod_version_path, file)
                extraction_path = join(root_path, "build", file + "_extraction")
                if exists(extraction_path):
                    rmtree(extraction_path)
                if not exists(extraction_path):
                    mkdir(extraction_path)
                cmd_line_gdb = '{} -x"{}" "*.gdb" -o{}'.format(
                    modmgr_path, full_mas_path, extraction_path
                )
                cmd_line_wet = '{} -x"{}" "*.wet" -o{}'.format(
                    modmgr_path, full_mas_path, extraction_path
                )
                cmd_line_grip = '{} -x"{}" "*.rrbin" -o{}'.format(
                    modmgr_path, full_mas_path, extraction_path
                )
                subprocess.check_output(cmd_line_gdb)
                subprocess.check_output(cmd_line_wet)
                subprocess.check_output(cmd_line_grip)
                files_collected = listdir(extraction_path)
                grip_files = list(
                    filter(lambda x: ".rrbin" in x.lower(), files_collected)
                )
                grip_files.sort()
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
