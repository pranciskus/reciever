import subprocess
from os.path import join, exists, dirname
from os import listdir, unlink
from shutil import copy
import tempfile
from pathlib import Path
from re import match
import logging

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
            steam_path + f" +force_install_dir {server_path} "
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
        command_line = command_line + " " + arg
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


def install_mod(server_config: dict, id: int, component_name: str) -> bool:
    root_path = server_config["server"]["root_path"]
    source_path = None
    if id > 0:
        steam_root = get_steamcmd_path(server_config)
        source_path = join(
            steam_root, "steamapps\\workshop\\content\\365960\\", str(id)
        )
    else:
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
    logging.info(
        "Choosing source path {} for component {}".format(source_path, component_name)
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
    mod_mgr_cmdline = f"{root_path}\\server\\Bin64\\ModMgr.exe -c{root_path}\\server\\"

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

    return list(filter(lambda r: not r, install_results)) == []
