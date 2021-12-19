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
from string import ascii_uppercase, digits
from random import choice
from psutil import process_iter
import tarfile
from sys import platform
if platform == "linux":
    from rf2.wine import Popen
else:
    from subprocess import Popen

def oneclick_start_server(server_config: dict, files: dict) -> bool:
    root_path = server_config["server"]["root_path"]

    try:
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
        
        if platform == "win32":
            from subprocess import HIGH_PRIORITY_CLASS
            Popen(server_binary_commandline, creationflags=HIGH_PRIORITY_CLASS)
        else:
            Popen(server_binary_commandline)
        if server_config["mod"]["real_weather"]:
            # start the weather_client
            weather_client_root = join(server_config["server"]["root_path"], "weatherclient")
            weather_command_line =  join(weather_client_root, "rf2WeatherClient.exe")
            Popen(weather_command_line, cwd=weather_client_root)


    except Exception as e:
        from traceback import print_exc

        print_exc()
    # generate files for APX clients
    output_filename = join(root_path, "modpack.tar.gz")
    with tarfile.open(output_filename, "w:gz") as tar:
        # add the manifest
        manifest_name = join(
            "Manifests",
            files["mod"]["Name"]
            + "_"
            + files["mod"]["Version"].replace(".", "")
            + ".mft",
        )
        manifest_path = join(root_path, "server", manifest_name)
        tar.add(manifest_path, manifest_name)

        # add the rfm mas path
        rfm_name = join(
            "Installed",
            "rFm",
            files["mod"]["Name"]
            + "_"
            + files["mod"]["Version"].replace(".", "")
            + ".mas",
        )
        rfm_path = join(root_path, "server", rfm_name)
        tar.add(rfm_path, rfm_name)

        # Add track files
        for signature in files["signatures"]:
            if "files" in signature:
                signature_root_path = join(
                    "Installed",
                    "Vehicles" if int(signature["Type"]) == 2 else "Location",
                    signature["Name"],
                    signature["Version"],
                )
                full_signature_path = join(root_path, "server", signature_root_path)
                for file in signature["files"]:
                    tar.add(
                        join(full_signature_path, file), join(signature_root_path, file)
                    )

    return True


def stop_server(server_config: dict) -> bool:
    """
    Stops the server

    Args:
        server_config: The global configuration for this instance

    Returns:
        The success of the operation
    """
    real_weather = server_config["mod"]["real_weather"]

    root_path = join(server_config["server"]["root_path"], "server")
    binary_path = join(root_path, "Bin64", "rFactor2 Dedicated.exe")
    weather_binary_path = join(server_config["server"]["root_path"], "weatherclient", "rf2WeatherClient.exe")
    chat(server_config, "Server is shutting down NOW")
    do_action(server_config, Action.RESTARTWEEKEND)
    sleep(5)  # Give the server a chance to react
    server_killed = False
    weatherclient_killed = not real_weather
    for proc in process_iter():
        name = proc.name()
        if "rFactor" in name:
            exe = proc.exe()
            if exe == binary_path:
                proc.kill()
                server_killed = True
        if real_weather and "rf2WeatherClient" in name:
            exe = proc.exe()
            if exe == weather_binary_path:
                proc.kill()
                weatherclient_killed = True
        
        if server_killed and weatherclient_killed:
            return True
    return False