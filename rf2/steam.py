import subprocess
from os.path import join, exists, dirname, getsize
from os import listdir, unlink, mkdir
from shutil import copy
import tempfile
from pathlib import Path
from re import match
import logging
import sys

LINK_MODS = True

STEAMCMDCOMMANDS = {
    "add": f"+login anonymous +workshop_download_item 365960",
    "update": f"+login anonymous +app_update 400300 ",
    "install": f"+login anonymous +app_update 400300 ",
}


"""
The reciever can probably work without copying steam workshop items into packages/
"""
DONT_COPY_INTO_PACKAGES = True


def get_steamcmd_path(server_config):
    root_path = server_config["server"]["root_path"]
    global_steam_path = join(root_path, "steamcmd")
    if "global_steam_path" in server_config["mod"]:
        global_steam_path = server_config["mod"]["global_steam_path"]
        logging.info(
            f"The server runs in a wizard instance with a global steam instance. We will use {global_steam_path} as the root for steamcmd."
        )

    return global_steam_path


def run_steamcmd(server_config: dict, command: str, arg: str = None) -> bool:
    """
    Runs the given steam cmd from STEAMCMDCOMMANDS
    returns if the operation is successfully
    """
    logging.info("Triggering steam command: {}, args: {}".format(command, arg))
    root_path = server_config["server"]["root_path"]
    global_steam_path = get_steamcmd_path(server_config)
    steam_path = join(global_steam_path, "steamcmd.exe")
    server_path = join(root_path, "server")

    if command == "install" or command == "update":
        branch = server_config["mod"]["branch"]
        command_line = (
            '"' + steam_path + f'" +force_install_dir "{server_path}" '
            " " + STEAMCMDCOMMANDS[command] + " -beta " + branch
        )
    else:
        command_line = steam_path + " " + STEAMCMDCOMMANDS[command]
    bandwidth = (
        server_config["mod"]["steamcmd_bandwidth"]
        if "steamcmd_bandwidth" in server_config["mod"]
        else 0
    )
    if bandwidth > 0:
        logging.info("Enforcing steam bandwidth limit by {} kbit/s".format(bandwidth))
        command_line = command_line.replace(
            "+login anonymous",
            "+login anonymous +set_download_throttle {}".format(bandwidth),
        )

    if arg is not None:
        command_line = command_line + " " + str(arg)
    command_line = command_line + f" +quit"
    try:
        logging.info("Running shell command {}".format(command_line))
        p = subprocess.Popen(command_line, shell=True, stderr=subprocess.PIPE)
        while True:
            out = p.stderr.read(1).decode("utf-8")
            if out == "" and p.poll() != None:
                break
            if out != "":
                sys.stdout.flush()
        logging.info(
            "Shell command {} returned error code {}".format(command_line, p.returncode)
        )
        return p.returncode == 0
    except Exception as e:
        logging.error("Recieved error while executing steamcmd {}".format(e))
        return False


def get_mod_files_from_steam(server_config: dict, id: str) -> list:
    """
    Lists all rfcmp files from a workshop package (must be downloaded)
    """
    root_path = get_steamcmd_path(server_config)
    source_path = join(root_path, "steamapps\\workshop\\content\\365960\\", id)
    return get_mod_files_from_folder(source_path)


def get_mod_files_from_folder(source_path: str) -> list:
    """
    Lists all rfcmp files from folder
    """
    if not exists(source_path):
        logging.warning(f"The path {source_path} is not existing")
        return []
    return list(filter(lambda r: ".rfcmp" in r, listdir(source_path)))


def extract_veh_files(root_path, component_name: str, version: str):
    temp_path = tempfile.mkdtemp()
    comp_path = join(
        root_path, "server", "Installed", "Vehicles", component_name, version
    )
    logging.info(
        "Trying to extract the vehicle definitions for component {}".format(
            component_name
        )
    )
    if not exists(comp_path):
        logging.info("The mod {} does not exists".format(comp_path))
        return []
    mod_mgr_path = join(root_path, "server", "Bin64", "ModMgr.exe")
    files = list(Path(comp_path).rglob("*.mas"))
    for file in files:
        cmd_line_extract = '{} -x"{}" "*.veh" -o"{}"'.format(
            mod_mgr_path, file, temp_path
        )
        logging.info(
            "Executing command {} for vehicle extraction".format(cmd_line_extract)
        )
        p = subprocess.Popen(cmd_line_extract, shell=True, stderr=subprocess.PIPE)
        return_code = p.wait()
        if return_code != 0:
            raise Exception(
                "We did not manage to extract any vehicle definitions. Check the used version."
            )
    veh_files = listdir(temp_path)

    results = []
    for veh_file in veh_files:
        results.append(join(temp_path, veh_file))
    return results


def extract_gdb_files(root_path, component_name: str, version: str):
    temp_path = tempfile.mkdtemp()
    comp_path = join(
        root_path, "server", "Installed", "Locations", component_name, version
    )
    logging.info(
        "Trying to extract the layout names for component {}".format(component_name)
    )
    if not exists(comp_path):
        logging.info("The mod {} does not exists".format(comp_path))
        return []
    mod_mgr_path = join(root_path, "server", "Bin64", "ModMgr.exe")
    files = list(Path(comp_path).rglob("*.mas"))
    for file in files:
        cmd_line_extract = '{} -x"{}" "*.gdb" -o"{}"'.format(
            mod_mgr_path, file, temp_path
        )
        logging.info(
            "Executing command {} for layout extraction".format(cmd_line_extract)
        )
        p = subprocess.Popen(cmd_line_extract, shell=True, stderr=subprocess.PIPE)
        return_code = p.wait()
        if return_code != 0:
            raise Exception(
                "We did not manage to extract any layout definitions. Check the used version."
            )

    gdb_files = listdir(temp_path)

    results = []
    for gdb_file in gdb_files:
        results.append(join(temp_path, gdb_file))
    return results


def get_layouts(root_path, component_name: str, version: str):
    gdb_files = extract_gdb_files(root_path, component_name, version)
    logging.info("Found {} files as gdb definition".format(len(gdb_files)))
    if len(gdb_files) == 0:
        logging.exception(
            "We did not manage to extract any layout definitions. Check the used version."
        )
        raise Exception(
            "We did not manage to extract any layout definitions. Check the used version."
        )
    entries = []
    for file in gdb_files:
        full_path = join(file)
        with open(full_path, "r") as gdb_handle:
            content = gdb_handle.readlines()
            result = {"EventName": None, "TrackName": None, "TrackNameShort": None}
            for line in content:
                needles = result.keys()
                for needle in needles:
                    if needle in line:
                        parts = line.split("=")
                        layout = parts[1].lstrip().replace("\n", "")
                        result[needle] = layout

            entries.append(result)
    return entries


def get_entries_from_mod(root_path, component_name: str, version: str):
    veh_files = extract_veh_files(root_path, component_name, version)
    logging.info("Found {} files as vehicle definition".format(len(veh_files)))
    if len(veh_files) == 0:
        logging.exception(
            "We did not manage to extract any vehicle definitions. Check the used version."
        )
        raise Exception(
            "We did not manage to extract any vehicle definitions. Check the used version."
        )
    pattern = r"Description\s{0,}=\s{0,}\"(.+)\""
    entries = []
    for file in veh_files:
        full_veh_path = join(file)
        with open(full_veh_path, "r") as veh_handle:
            content = veh_handle.readlines()
            for line in content:
                got = match(pattern, line)
                if got:
                    description = got.group(1)
                    entries.append(description)
    return entries


def find_source_path(root_path: str, component_name: str):
    source_path = None
    if "server_children" in root_path:
        # the server runs in a managed environment
        # get new root path, basically do a doubled "cd .."
        new_root_path = dirname(dirname(root_path))
        source_path = join(new_root_path, "uploads", "items", component_name)
        logging.info(
            f"The server runs in a managed environment. The items root for this will be defined as {source_path}"
        )
        if not exists(source_path):
            logging.error(
                f"The folder for non workshop item {source_path} does not exists."
            )
            raise Exception("Failed to install mod. Check log")
    else:
        source_path = join(root_path, "items", component_name)
    return source_path


def install_mod(
    server_config: dict, id: int, component_name: str, ignore_links: bool = False
) -> bool:
    root_path = server_config["server"]["root_path"]
    use_global_steam = "global_steam_path" in server_config["mod"]
    steam_root = get_steamcmd_path(server_config)
    mod_dump_path = join(steam_root, "mod_dump")
    if not ignore_links and LINK_MODS and not exists(mod_dump_path):
        mkdir(mod_dump_path)
    mod_path = join(mod_dump_path, str(id))
    if not ignore_links and LINK_MODS and not exists(mod_path):
        mkdir(mod_path)

    source_path = None
    if id > 0:
        source_path = join(
            steam_root, "steamapps\\workshop\\content\\365960\\", str(id)
        )
    else:
        source_path = find_source_path(root_path, component_name)
    if component_name is not None:
        logging.info(
            "Choosing source path {} for component {}".format(
                source_path, component_name
            )
        )

    files = (
        get_mod_files_from_steam(server_config, str(id))
        if id > 0
        else get_mod_files_from_folder(source_path)
    )
    logging.info("Found {} files in {}".format(len(files), source_path))
    # copy files into rf2 packages dir
    copy_results = []
    for rf_mod in files:
        if DONT_COPY_INTO_PACKAGES:
            rfmod_full_path = join(source_path, rf_mod)
            copy_results.append(rfmod_full_path)
        else:
            rfmod_full_path = join(source_path, rf_mod)
            rfmod_target_path = join(root_path, "server\\Packages")

            rfmod_target_full_path = join(rfmod_target_path, rf_mod)
            copy(rfmod_full_path, rfmod_target_path)
            copy_results.append(rfmod_target_full_path)

    # install the mod into rf2 itself
    mod_mgr_cmdline = (
        f"{root_path}\\server\\Bin64\\ModMgr.exe -c{root_path}\\server\\"
        if not LINK_MODS and not ignore_links
        else f"{root_path}\\server\\Bin64\\ModMgr.exe -c{mod_dump_path}\\{id}"
    )

    install_results = []
    for rf_mod in copy_results:
        logging.info(
            "Running modmgr command {}".format(mod_mgr_cmdline + " -q -i" + rf_mod)
        )
        install = subprocess.getstatusoutput(
            mod_mgr_cmdline + ' -q -i"' + rf_mod + "\n"
        )
        if install[0] != 0:
            logging.warning(f"ModMgr returned {install[0]} as a returncode.")
        install_results.append(install[0] == 0)
    if LINK_MODS and not ignore_links:
        logging.info(
            f"Attempting to create links for the mod contents to the server root {root_path}"
        )
        mod_content_path = join(mod_path, "Installed")
        mod_content_types = listdir(mod_content_path)
        for type_dir in mod_content_types:  # Vehicles, Locations etc.
            full_type_path = join(mod_content_path, type_dir)
            mod_type_contents = listdir(full_type_path)
            target_parent_folder = join(root_path, "server", "Installed", type_dir)
            if not exists(target_parent_folder):
                mkdir(target_parent_folder)
            for folder in mod_type_contents:
                target_parent_folder = join(
                    root_path, "server", "Installed", type_dir, folder
                )
                if not exists(target_parent_folder):
                    mkdir(target_parent_folder)
                full_src_path = join(full_type_path, folder)
                versions_content = listdir(full_src_path)
                for version in versions_content:
                    version_src_path = join(full_src_path, version)
                    files_in_version = listdir(version_src_path)
                    manifest_file_empty = False
                    for found_file in files_in_version:
                        if ".mft" in found_file:
                            full_mft_path = join(version_src_path, found_file)
                            if getsize(full_mft_path) == 0:
                                manifest_file_empty = True
                                break

                    if len(files_in_version) > 0 or not manifest_file_empty:
                        full_target_path = join(
                            root_path, "server", "Installed", type_dir, folder, version
                        )
                        logging.info(
                            f"Linking {version_src_path} to {full_target_path}"
                        )
                        mklink_cmdline = (
                            f"mklink /J {full_target_path} {version_src_path}"
                        )
                        logging.info(f"Commandline: {mklink_cmdline}")
                        subprocess.Popen(
                            mklink_cmdline,
                            shell=True,
                            stderr=subprocess.PIPE,
                        )
                    else:
                        logging.warn(
                            f"Linking {version_src_path} to {full_target_path} aborted. The folder {version_src_path} was empty. We will re-attempt"
                        )
                        install_mod(server_config, id, component_name, True)

    return list(filter(lambda r: not r, install_results)) == []
