import subprocess
from os.path import join, exists
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


def run_steamcmd(server_config: dict, command: str, arg: str = None) -> bool:
    """
    Runs the given steam cmd from STEAMCMDCOMMANDS
    returns if the operation is successfully
    """
    logging.info("Triggering steam command: {}, args: {}".format(command, arg))
    root_path = server_config["server"]["root_path"]
    steam_path = join(root_path, "steamcmd", "steamcmd.exe")
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
    root_path = server_config["server"]["root_path"]
    source_path = join(
        root_path, "steamcmd\\steamapps\\workshop\\content\\365960\\", id
    )
    return get_mod_files_from_folder(source_path)


def get_mod_files_from_folder(source_path: str) -> list:
    """
    Lists all rfcmp files from folder
    """
    if not exists(source_path):
        return []
    return list(filter(lambda r: ".rfcmp" in r, listdir(source_path)))


def get_entries_from_mod(root_path, component_name: str, version: str):
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
        cmd_line_extract = '{} -x{} "*.veh" -o{}'.format(mod_mgr_path, file, temp_path)
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
    logging.info(
        "Found {} files as vehicle definition in {}".format(len(veh_files), temp_path)
    )
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
        full_veh_path = join(temp_path, file)
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
        source_path = join(
            root_path, "steamcmd\\steamapps\\workshop\\content\\365960\\", str(id)
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
        install = subprocess.getstatusoutput(mod_mgr_cmdline + " -q -i" + rf_mod)
        if install[0] != 0:
            logging.warning(f"ModMgr returned {install[0]} as a returncode.")
        install_results.append(install[0] == 0)

    return list(filter(lambda r: not r, install_results)) == []
