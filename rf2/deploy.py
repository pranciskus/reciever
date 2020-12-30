from os.path import join, exists
from os import listdir, mkdir, getenv, unlink
from shutil import copy, rmtree, copytree, move
from rf2.steam import run_steamcmd, install_mod
import subprocess
from time import sleep
from json import loads, dumps, load, dump
import re
from distutils.version import LooseVersion

VERSION_SUFFIX = ".9apx"


def deploy_server(server_config: dict, rfm_contents: str, weather_data, grip_data) -> bool:
    vehicles = server_config["mod"]["cars"]
    tracks = server_config["mod"]["track"]
    mod_info = server_config["mod"]["mod"]
    conditions = server_config["mod"]["conditions"] if "conditions" in server_config["mod"] else None
    root_path = server_config["server"]["root_path"]

    restore_vanilla(server_config)
    root_path = server_config["server"]["root_path"]
    # build vehicle mods
    for workshop_id, vehicle in vehicles.items():
        run_steamcmd(server_config, "add", workshop_id)
        install_mod(server_config, workshop_id)
        component_info = vehicle["component"]
        if component_info["update"]:
            create_mas(server_config, component_info, True)
            build_cmp_mod(server_config, component_info, "Vehicles", True)

    used_track = None
    for workshop_id, track in tracks.items():
        used_track = track
        run_steamcmd(server_config, "add", workshop_id)
        install_mod(server_config, workshop_id)
        # TODO cmd mods are not supported yet.
    build_mod(server_config, vehicles, used_track, mod_info, rfm_contents)

    create_conditions(root_path, weather_data, grip_data, conditions)
    return True


def create_conditions(root_path: str, weather, grip, conditions) -> bool:
    if conditions is None:
        # conditions may be not configured at all
        return True

    server_root = join(root_path, "server")
    conditions_root = conditions["conditionsRoot"]
    weather_file_name = conditions["weatherTarget"]
    condition_files_root_path = join(
        server_root, "UserData", "player", "Settings", conditions_root)
    if not exists(condition_files_root_path):
        mkdir(condition_files_root_path)
    # save weather file
    weather_file_path = join(condition_files_root_path, weather_file_name)
    weather.save(weather_file_path)

    with open(weather_file_path, "r") as weather_file:
        content = weather_file.read()
        for key, value in grip.items():
            print(key, value)
            content = re.sub(r"{}=\".+\"".format(key),
                             "{}=\"{}\"".format(key, key + ".rrbin"), content)
            grip_file_path = join(condition_files_root_path, key + ".rrbin")
            value.save(grip_file_path)

        with open(weather_file_path, "w") as weather_write_handle:
            weather_write_handle.write(content)

    return True


def get_latest_version(root_path: str, latest=True) -> str:
    versions = listdir(root_path)
    versions.sort(key=LooseVersion)
    if len(versions) == 0:
        raise Exception("There are no versions to choose from")
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


def build_mod(server_config: dict, vehicles: dict, track: dict, mod_info: dict, rfm_contents: str):
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
                join(root_path, "server", "Installed", "Vehicles", name), version == "latest")
            print("Using", version,  "as mod version for item", name)

        version = version if not component["update"] else version + \
            VERSION_SUFFIX
        line = "Vehicle=\"" + name + " v" + version + ",0\""
        for entry in vehicle["entries"]:
            line = line + " \"" + entry + ",1\""

        veh_contents = veh_contents + line + "\n"

    # multiple tracks are not supported
    track_components = track["component"]

    if track_components["version"] == "latest" or track_components["version"] == "latest-even":
        track_components["version"] = get_latest_version(
            join(root_path, "server", "Installed", "Locations", track_components["name"]), track_components["version"] == "latest")
        print("Using", track_components["version"],  "as mod version for item",
              track_components["name"])

    replacements = {
        "mod_name": mod_info["name"],
        "mod_version": mod_info["version"],
        "trackmod_name": track_components["name"],
        "trackmod_version": "v" + track_components["version"],
        "layouts": "\"" + track["layout"] + ",1\"",
        "location": join(root_path, "server", "Packages", mod_info["name"] + ".rfmod"),
        "veh_mods_count": str(len(vehicles)),
        "veh_mod_contents": veh_contents,
        "build_path": join(root_path, "build")
    }
    for key, value in replacements.items():
        data = data.replace("#" + key, value)

    pkg_info_path = join(getenv('APPDATA'), "pkginfo.dat")
    # write data
    with open(pkg_info_path, 'w') as cmp_write:
        cmp_write.write(data)

    # build rfm mas
    rfm_build_path = join(root_path, "build", mod_info["name"] + "_rfm")
    if exists(rfm_build_path):
        rmtree(rfm_build_path)
    mkdir(rfm_build_path)
    copy("templates/rFm/icon.dds", join(rfm_build_path, "icon.dds"))
    copy("templates/rFm/smicon.dds", join(rfm_build_path, "smicon.dds"))
    with open(join(rfm_build_path, "default.rfm"), 'w') as rFm_write:
        rFm_write.write(rfm_contents)

    rfm_mas_path = join(root_path, "build",  mod_info["name"] + ".mas")
    rfmod_path = join(root_path, "server", "Packages",
                      mod_info["name"] + ".rfmod")
    build_mas(server_config, rfm_build_path, rfm_mas_path)
    server_root_path = join(root_path, "server")
    run_modmgr_build(server_root_path, pkg_info_path)
    run_modmgr_install(server_root_path, rfmod_path)


def run_modmgr_build(server_root_path: str, pkg_info_path: str):
    modmgr_path = join(server_root_path, "Bin32\\ModMgr.exe")
    cmd_line = [
        modmgr_path,
        f'-c{server_root_path}',
        f'-b{pkg_info_path}',
        "0",
    ]
    build = subprocess.Popen(cmd_line, shell=False, cwd=server_root_path,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def run_modmgr_install(server_root_path: str, pkg_path: str):
    sleep(2)  # TODO: Make sure install actions are actually done
    modmgr_path = join(server_root_path, "Bin32\\ModMgr.exe")
    cmd_line = [
        modmgr_path,
        f"-c{server_root_path}",
        "-q",
        f'-i{pkg_path}',
    ]
    build = subprocess.Popen(cmd_line, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def build_cmp_mod(server_config, component_info: dict, packageType: str = "Vehicles", add_version_suffix=False):
    root_path = server_config["server"]["root_path"]
    name = component_info["name"]
    version = component_info["version"]
    update_version = version + VERSION_SUFFIX

    base_target_path = join(
        root_path, f"server\\Installed\\Vehicles\\{name}\\{version}")
    target_path = join(
        root_path, f"server\\Installed\\Vehicles\\{name}\\{update_version}")

    if not add_version_suffix:
        mas_path = join(root_path, "build",  f"{name}.mas")
    else:
        mas_path = join(root_path, "build",
                        f"{name}_v{version}{VERSION_SUFFIX}.mas")

    # inject dat in cmpinfo
    data = ""
    with open("templates/cmpinfo.dat") as f:
        data = f.read()

    # replace values from parameters
    # TODO LOCATION -> MAYBE THE LOCATION IN PACKAGES (fullpath)
    public_ip = server_config["server"]["public_ip"]
    public_port = server_config["server"]["port"]
    # "http://localhost:8081/Bentley_Continental_GT3_2020_2020_v1.051apx.rfcmp"
    mod_download_url = f"http://{public_ip}:{public_port}/"
    location_path = join(
        root_path, f"server\\Packages\\{name}_v{update_version}.rfcmp")
    data = data.replace("component_name", name).replace("mod_version", update_version).replace(
        "base_version", version).replace("mas_file", mas_path).replace("location", location_path).replace("mod_download_url", "http://localhost:8081/Bentley_Continental_GT3_2020_2020_v1.051apx.rfcmp")

    cmp_file = join(getenv('APPDATA'), "cmpinfo.dat")
    with open(cmp_file, 'w') as cmp_write:
        cmp_write.write(data)
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

    # remove steam workshop items
    steam_packages_path = join(
        server_root_path, "steamapps", "workshop", "content", "365960")
    if exists(steam_packages_path):
        rmtree(steam_packages_path)

    # Overwrite player.json and multiplayer.json
    user_data_path = join(server_root_path, "UserData")
    profile_path = join(user_data_path, "player")
    copy("templates/player.JSON", join(profile_path, "player.JSON"))
    copy("templates/Multiplayer.JSON", join(profile_path, "Multiplayer.JSON"))
    overwrites = server_config["mod"]["server"]["overwrites"]
    for overwrite_file, overwrite_options in overwrites.items():
        full_path = join(profile_path, overwrite_file)
        parsed = load(open(full_path, "r"))
        for option, options in overwrite_options.items():
            for option_key, option_value in options.items():
                parsed[option][option_key] = option_value
        with open(full_path, "w") as overwrite_file_handle:
            overwrite_file_handle.write(
                dumps(parsed, indent=4, separators=(',', ': ')))

    folder_paths = {
        join(user_data_path, "Replays"): [],
        join(user_data_path, "Log"): ["CBash", "Results", "Shaders"],
        join(server_root_path, "Packages"): ["Skins"],
        join(server_root_path, "appcache"): [],
        join(server_root_path, "steamapps"): [],
        join(user_data_path, "player", "Settings"): []
    }

    for folder_path, folders in folder_paths.items():
        if exists(folder_path):
            rmtree(folder_path)
        mkdir(folder_path)
        if len(folders) > 0:
            for sub_folder in folders:
                sub_folder_path = join(folder_path, sub_folder)
                mkdir(sub_folder_path)

    # Overwrite installed an manifests
    template_copy_paths = {
        "templates/Installed":  join(server_root_path, "Installed"),
        "templates/Manifests":  join(server_root_path, "Manifests")
    }

    for path, target_path in template_copy_paths.items():
        if exists(target_path):
            rmtree(target_path)

        copytree(path, target_path)
    # Update the server itself using steam
    run_steamcmd(server_config, "update")


def create_mas(server_config: dict, component_info: dict, add_version_suffix=False):
    root_path = server_config["server"]["root_path"]
    build_path = join(root_path, "build")
    component_path = join(build_path, component_info["name"])
    if not add_version_suffix:
        target_path = join(build_path, component_info["name"] + ".mas")
    else:
        target_path = join(
            build_path, component_info["name"] + "_v" + component_info["version"] + VERSION_SUFFIX + ".mas")
    build_mas(server_config, component_path, target_path)


def build_mas(server_config: dict, source_path: str, target_path: str):
    """
    Add files from a given directory to a MAS file
    """
    root_path = server_config["server"]["root_path"]

    files_to_add = listdir(source_path)
    cmd_line = f"{root_path}\\server\\Bin32\\ModMgr.exe -m" + \
        target_path + " " + join(source_path, "*.*")

    build = subprocess.getstatusoutput(cmd_line)
    # keep casing
    lowercase_path = join(root_path, "build", target_path.lower())
    move(lowercase_path, target_path)
    return build[0] != 0
