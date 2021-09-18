from requests import get
from zipfile import ZipFile
from rf2.steam import run_steamcmd
from os.path import join, dirname, exists
from subprocess import Popen
from time import sleep
import logging

STEAMCMD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"


def install_server(server_config: dict) -> bool:
    root_path = server_config["server"]["root_path"]
    install_steam = True
    if "server_children" in root_path:
        # the server runs in a managed environment
        # get new root path, basically do a doubled "cd .."
        new_root_path = dirname(dirname(root_path))
        if exists(new_root_path, "steamcmd", "steamcmd.exe"):
            steam_root = join(new_root_path, "steamcmd")
            logging.info(
                "We will skip the download of the steamcmd command set as there is a global steamcmd apparently."
            )
            logging.info(f"Injecting {steam_root} as global steam path root")
            server_config["mod"]["global_steam_path"] = steam_root
            install_steam = False

    if install_steam:
        steamcmd_path = join(root_path, "steamcmd.zip")
        steamcmd_folder_path = join(root_path, "steamcmd")
        r = get(STEAMCMD_URL)

        with open(steamcmd_path, "wb") as f:
            f.write(r.content)

        zf = ZipFile(steamcmd_path, "r")
        zf.extractall(steamcmd_folder_path)
        zf.close()
    run_steamcmd(server_config, "install")
    # start the server
    server_root_path = join(root_path, "server")

    server_path = (
        join(server_root_path, "Bin64", "rFactor2 Dedicated.exe")
        + f' +path="{server_root_path}"'
    )
    got = Popen(server_path)
    sleep(2)
    got.kill()
    return True
