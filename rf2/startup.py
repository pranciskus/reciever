from os.path import join, exists
from os import remove
from time import sleep
from rf2.util import (
    get_server_port,
    get_max_players,
)
from rf2.interaction import chat, do_action, Action
from rf2.deploy import update_weather
import logging
from subprocess import Popen, STARTUPINFO, HIGH_PRIORITY_CLASS
from string import ascii_uppercase, digits
from random import choice
from psutil import process_iter


def oneclick_start_server(server_config: dict) -> bool:
    root_path = server_config["server"]["root_path"]
    server_root_path = join(server_config["server"]["root_path"], "server")
    mod = server_config["mod"]["mod"]
    server_binary_path = join(server_root_path, "Bin64", "rFactor2 Dedicated.exe")
    server_binary_commandline = (
        server_binary_path
        + f' +path="{server_root_path}"'
        + f"  +profile=player  +oneclick"
    )

    track = server_config["mod"]["track"][next(iter(server_config["mod"]["track"]))]
    name = track["component"]["name"]
    layout = track["layout"]
    logging.info(f"Using {name}:{layout} for startup")

    session_id_path = join(root_path, "reciever", "session_id.txt")

    with open(session_id_path, "w") as file:
        file.write("".join(choice(ascii_uppercase + digits) for _ in range(25)))

    # make sure the Dedicated<modname>.ini has the correct content
    mod_ini_path = join(
        server_root_path, "UserData", "player", "Dedicated" + mod["name"] + ".ini"
    )

    max_clients_overwrite = get_max_players(server_config)

    if exists(mod_ini_path):
        remove(mod_ini_path)
    with open(mod_ini_path, "w") as file:
        file.write("[SETTINGS]\n")
        file.write("MaxClients=" + str(max_clients_overwrite) + "\n")
        file.write("[TRACKS]\n")
    Popen(server_binary_commandline, creationflags=HIGH_PRIORITY_CLASS)
    return True


def stop_server(server_config: dict) -> bool:
    """
    Stops the server

    Args:
        server_config: The global configuration for this instance

    Returns:
        The success of the operation
    """

    root_path = join(server_config["server"]["root_path"], "server")
    binary_path = join(root_path, "Bin64", "rFactor2 Dedicated.exe")
    chat(server_config, "Server is shutting down NOW")
    do_action(server_config, Action.RESTARTWEEKEND)
    sleep(5)  # Give the server a chance to react

    for proc in process_iter():
        name = proc.name()
        if "rFactor" in name:
            exe = proc.exe()
            if exe == binary_path:
                proc.kill()
                return True
    return False