from os.path import join, exists
from os import remove
from time import sleep

from pywinauto import Application, WindowSpecification
from rf2.util import (
    set_slider_value,
    set_updown_value,
    select_from_list,
    set_window_elements_value,
    get_server_port,
    get_max_players,
)
from rf2.interaction import chat, do_action, Action
from rf2.deploy import update_weather
import logging
from subprocess import Popen, STARTUPINFO, HIGH_PRIORITY_CLASS
from string import ascii_uppercase, digits
from random import choice


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

    if server_config["mod"]["real_weather"]:
        update_weather(root_path, server_config["mod"]["sessions"], name, layout)

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
    chat(server_config, "Server is shutting down NOW")

    do_action(server_config, Action.RESTARTWEEKEND)
    root_path = join(server_config["server"]["root_path"], "server")
    binary_path = join(root_path, "Bin64", "rFactor2 Dedicated.exe")
    app = Application(backend="uia")
    app.connect(path=binary_path)
    app.kill()
    return True


def select_mod_and_admin_password(
    window: WindowSpecification, admin_password: str, mod_name: str, mod_version: str
):
    """
    Select the mod and inserts the admin password

    Args:
        window: WindowSpecification
        admin_password: The admin password string
        mod_name: The mod name string
        mod_version: The mod version: Important: WITHOUT a "v" prefix!
    """
    mod_Box = window.window(
        best_match="Select which game database to use for this server:ComboBox"
    )
    mods = mod_Box.item_texts()
    mod_Box.select(mods.index(f"{mod_name} v{mod_version}"))

    window.window(best_match="Edit").set_text(admin_password)


def select_grip(
    start_window: WindowSpecification,
    grips: dict,
    tracks: dict,
    server_root_path: str,
    rf2_server: Application,
):
    """
    Select the mod and inserts the admin password

    Args:
        start_window: WindowSpecification
        grips: A dictionary containing the session keyed grip infos
        tracks: The workshop_id keyed track infos
        server_root_path: The root path of the server
        rf2_server: The Application instance of the rf2 server
    """

    # select the track
    for _, track in tracks.items():
        layout = track["layout"]
        event_list = start_window.window(best_match="Selected Events:ListBox")
        select_from_list(event_list, [layout])
        sleep(1)
        # open weather and grip window
        start_window.window(best_match="Weather").click()
        grip_window = rf2_server.window(best_match=server_root_path)
        grip_window.wait("visible")
        grip_window.minimize()

        # Select the grip itself
        session_select = grip_window.window(best_match="ComboBox11")
        grip_mode_select = grip_window.window(best_match="Real Road:ListBox")
        grip_scale_select = grip_window.window(
            best_match="Real Road Time Scale:ComboBox13"
        )
        for session, grip in grips.items():
            grip_mode = grip["grip_mode"]
            grip_scale = grip["grip_scale"]
            select_from_list(session_select, [session])
            select_from_list(grip_mode_select, [grip_mode])
            select_from_list(grip_scale_select, [grip_scale])

        grip_window.window(best_match="Save").click()
