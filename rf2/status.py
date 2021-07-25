import re
from os.path import join, isfile, exists
from time import time
from requests import get
from requests.exceptions import RequestException
from json import load
from rf2.util import get_server_port, get_public_http_server_port
import logging
from os import listdir
from time import time
from time import time


def get_server_mod(server_config: dict) -> dict:
    target_url = "http://localhost:{}".format(get_server_port(server_config))
    try:
        mod_content = get(target_url + "/rest/race/car").json()
        return mod_content
    except:
        return None


def get_server_status(server_config: dict) -> dict:
    """
    Get the current server status

    Args:
        server_config: The global configuration for this instance

    Returns:
        A dictionary containing the current server state
    """
    target_url = "http://localhost:{}".format(get_server_port(server_config))
    unlock_path = join(
        server_config["server"]["root_path"],
        "server",
        "UserData",
        "ServerUnlock.bin",
    )
    is_unlocked = isfile(unlock_path)
    release_file_path = join(
        server_config["server"]["root_path"], "reciever", "release"
    )
    version_txt = join(
        server_config["server"]["root_path"], "server", "Core", "Version.txt"
    )
    deploy_lock_file_path = join(
        server_config["server"]["root_path"], "reciever", "deploy.lock"
    )

    results_path = join(
        server_config["server"]["root_path"], "server", "UserData", "Log", "Results"
    )
    replays_path = join(
        server_config["server"]["root_path"], "server", "UserData", "Replays"
    )
    session_id_path = join(
        server_config["server"]["root_path"], "reciever", "session_id.txt"
    )
    session_id = None

    if exists(session_id_path):
        with open(session_id_path, "r") as file:
            session_id = file.read()
    reciever_release = open(release_file_path, "r").read()
    result = None

    try:
        status_raw = get(target_url + "/rest/watch/sessionInfo").json()
        standings_raw = get(target_url + "/rest/watch/standings").json()
        waypoints = get(target_url + "/navigation/state").json()
        session_info_raw = get(target_url + "/rest/sessions").json()

        result = {
            "track": status_raw["trackName"],
            "name": status_raw["serverName"],
            "startEventTime": status_raw["startEventTime"],
            "currentEventTime": status_raw["currentEventTime"],
            "endEventTime": status_raw["endEventTime"],
            "flags": status_raw["sectorFlag"],
            "maxLaps": status_raw["maximumLaps"],
            "session": status_raw["session"],
            "vehicles": standings_raw,
            "keys": is_unlocked,
            "build": open(version_txt).readlines()[0].strip(),
            "release": reciever_release,
            "session_id": session_id,
            "weather": {
                "ambient": status_raw["ambientTemp"],
                "track": status_raw["trackTemp"],
                "rain": {
                    "min": status_raw["minPathWetness"],
                    "avg": status_raw["averagePathWetness"],
                    "max": status_raw["maxPathWetness"],
                    "raining": status_raw["raining"],
                    "dark_cloud": status_raw["darkCloud"],
                },
            },
            "waypoints": waypoints,
        }
        # unsure if always working, so in a try catch to prevent complete abort
        try:
            result["race_time"] = (
                session_info_raw["SESSSET_race_time"]["currentValue"] * 60
            )
            result["time_completion"] = status_raw["raceCompletion"]["timeCompletion"]
        except:
            pass
    except RequestException:
        result = None  # do nothing, if the server is not running
    except Exception as e:
        logging.error(e)
        result = None

    if not result:
        result = {
            "not_running": True,
            "keys": is_unlocked,
            "release": reciever_release,
        }
        if exists(deploy_lock_file_path):
            result["in_deploy"] = True

    result["replays"] = (
        list(
            filter(
                lambda x: "tmp" not in x and "apx-keep.txt" not in x,
                listdir(replays_path),
            )
        )
        if exists(replays_path)
        else []
    )
    result["results"] = (
        list(filter(lambda x: "xml" in x, listdir(results_path)))
        if exists(results_path)
        else []
    )

    return result
