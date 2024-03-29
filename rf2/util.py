from os.path import join, exists, sep
from os import getcwd, mkdir, pardir
from time import sleep
from json import load, dumps, loads
from random import randint
import secrets
import string
import socket
from pathlib import Path
from requests import get
from rf2.setup import install_server
from sys import platform
import logging


logger = logging.getLogger(__name__)


def get_main_window(server_config: dict):
    """
    Get the server main window

    This is not  available on Linux.

    Args:
        server_config: The global configuration for this instance

    Returns:
        A Desktop containing the dialog window.
    """
    if platform != "win32":
        raise Exception("This feature is not supported on Linux")
    from pywinauto import Desktop
    root_path = server_config["server"]["root_path"]
    server_root_path = join(root_path, "server") + "\\"
    dialog = Desktop(backend="win32").window(title=server_root_path)
    return dialog


def get_server_port(server_config: dict) -> int:
    player_json_path = join(
        server_config["server"]["root_path"],
        "server",
        "userData",
        "player",
        "player.JSON",
    )

    content = load(open(player_json_path, "r"))
    return content["Miscellaneous"]["WebUI port"]


def get_public_http_server_port(server_config: dict) -> int:
    multiplayer_json = join(
        server_config["server"]["root_path"],
        "server",
        "userData",
        "player",
        "Multiplayer.JSON",
    )

    content = load(open(multiplayer_json, "r"))
    return content["Multiplayer General Options"]["HTTP Server Port"]


def get_public_sim_server_port(server_config: dict) -> int:
    multiplayer_json = join(
        server_config["server"]["root_path"],
        "server",
        "userData",
        "player",
        "Multiplayer.JSON",
    )

    content = load(open(multiplayer_json, "r"))
    return content["Multiplayer General Options"]["HTTP Server Port"]


def get_max_players(server_config: dict) -> int:
    player_json_path = join(
        server_config["server"]["root_path"],
        "server",
        "userData",
        "player",
        "multiplayer.JSON",
    )

    content = load(open(player_json_path, "r"))
    return content["Multiplayer Server Options"]["Max MP Players"]


def get_free_tcp_port(max_tries=10, default_port=8000):
    port = default_port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for i in range(1, max_tries):
        try:
            s.connect(("localhost", int(port)))
            s.shutdown(2)
            port = randint(port, 65534)
        except:
            break
    return port


def get_secret(length=15):
    alphabet = string.ascii_letters + string.digits
    secret = "".join(secrets.choice(alphabet) for i in range(length))
    return secret


def create_config():
    current_cwd = getcwd()

    root_path = current_cwd
    reciever_path = join(current_cwd, "reciever.py")

    # if the file is already existing -> get correct root path, not "/reciever/reciever.py"
    if exists(reciever_path):
        root_path = str(Path(reciever_path).parent.parent.absolute())
    while not exists(reciever_path):
        logger.info("The current working directory does not contain the files we expected")
        logger.info("We expect following folder structure")
        logger.info("\server")
        logger.info("\\reciever")
        logger.info("\steamcmd")
        logger.info("\\build")
        root_path = input("Name the correct directory which contains the folders: ")
        reciever_path = join(root_path, "reciever", "reciever.py")

    if not root_path.endswith(sep):
        root_path += sep

    port = get_free_tcp_port(10, 8000)
    secret = get_secret()
    config_blob = {
        "root_path": root_path,
        "port": port,
        "host": "0.0.0.0",
        "auth": secret,
        "debug": False,
        "redownload_steam": False,
    }
    logger.info("APX will use this configuration")  #
    json_dump = dumps(config_blob, indent=4, sort_keys=True)
    logger.info(json_dump)
    server_path = join(root_path, "reciever", "server.json")
    with open(server_path, "w") as file:
        file.write(json_dump)
    setup_environment(root_path)


def setup_environment(root_path):
    config_path = join(root_path, "reciever", "server.json")
    mod_path = join(root_path, "reciever", "mod.json")
    build_path = join(root_path, "build")
    steamcmd_path = join(root_path, "steamcmd")
    # server_path = join(root_path, "steamcmd")

    # TODO: ad items folder

    if not exists(build_path):
        logger.info("Creating build path {}".format(build_path))
        mkdir(build_path)

    if not exists(steamcmd_path):
        logger.info("Creating steamcmd path {}".format(build_path))
        mkdir(steamcmd_path)

        with open(config_path, "r") as file:
            with open(mod_path, "r") as mod_file:
                config = {"mod": loads(mod_file.read()), "server": loads(file.read())}
                logger.info(config)
                install_server(config)
