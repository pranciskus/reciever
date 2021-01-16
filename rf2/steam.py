import subprocess
from os.path import join, exists
from os import listdir
from shutil import copy

STEAMCMDCOMMANDS = {
    "add": f"+login anonymous +workshop_download_item 365960",
    "update": f"+login anonymous +app_update 400300 +quit",
    "install": f"+login anonymous +app_update 400300 +quit",
}


def run_steamcmd(server_config: dict, command: str, arg: str = None) -> bool:
    """
    Runs the given steam cmd from STEAMCMDCOMMANDS
    returns if the operation is successfully
    """
    root_path = server_config["server"]["root_path"]
    steam_path = join(root_path, "steamcmd", "steamcmd.exe")
    server_path = join(root_path, "server")

    if command == "install" or command == "update":
        command_line = (
            steam_path + f" +force_install_dir {server_path} "
            " " + STEAMCMDCOMMANDS[command]
        )
    else:
        command_line = steam_path + " " + STEAMCMDCOMMANDS[command]

    if arg is not None:
        command_line = command_line + " " + arg
    command_line = command_line + f" +quit"
    try:
        p = subprocess.Popen(command_line, shell=True, stderr=subprocess.PIPE)
        while True:
            out = p.stderr.read(1).decode("utf-8")
            if out == "" and p.poll() != None:
                break
            if out != "":
                sys.stdout.flush()
        return p.returncode == 0
    except:
        return False


def get_mod_files_from_steam(server_config: dict, id: str) -> list:
    """
    Lists all rfcmp files from a workshop package (must be downloaded)
    """
    root_path = server_config["server"]["root_path"]
    source_path = join(
        root_path, "steamcmd\\steamapps\\workshop\\content\\365960\\", id
    )
    if not exists(source_path):
        return []
    return list(filter(lambda r: ".rfcmp" in r, listdir(source_path)))


def install_mod(server_config: dict, id: str) -> bool:
    root_path = server_config["server"]["root_path"]
    source_path = join(
        root_path, "steamcmd\\steamapps\\workshop\\content\\365960\\", id
    )

    files = get_mod_files_from_steam(server_config, id)
    # copy files into rf2 packages dir
    copy_results = []
    for rf_mod in files:
        rfmod_full_path = join(source_path, rf_mod)
        rfmod_target_path = join(root_path, "server\\Packages")

        rfmod_target_full_path = join(rfmod_target_path, rf_mod)
        copy(rfmod_full_path, rfmod_target_path)
        copy_results.append(rfmod_target_full_path)

    # install the mod into rf2 itself
    mod_mgr_cmdline = f"{root_path}\\server\\Bin32\\ModMgr.exe -c{root_path}\\server\\"

    install_results = []
    for rf_mod in copy_results:
        install = subprocess.getstatusoutput(mod_mgr_cmdline + " -q -i" + rf_mod)
        if install[0] != 0:
            logging.warning(f"ModMgr returned {install[0]} as a returncode.")
        install_results.append(install[0] == 0)

    return list(filter(lambda r: not r, install_results)) == []
