import re
from os.path import join
from time import time
from requests import get
from json import load


def get_server_port(server_config: dict) -> int:
    player_json_path = join(
        server_config["server"]["root_path"], "server", "userData", "player", "player.JSON")

    content = load(open(player_json_path, "r"))
    return content["Miscellaneous"]["WebUI port"]


def get_server_status(server_config: dict) -> dict:
    """
    Get the current server status

    Args:
        server_config: The global configuration for this instance

    Returns:
        A dictionary containing the current server state
    """

    target_url = "http://localhost:{}".format(get_server_port(server_config))
    result = None
    try:
        status_raw = get(target_url + "/rest/watch/sessionInfo").json()
        standings_raw = get(target_url + "/rest/watch/standings").json()
        result = {
            "track": status_raw["serverName"],
            "name": status_raw["trackName"],
            "startEventTime": status_raw["startEventTime"],
            "currentEventTime": status_raw["currentEventTime"],
            "endEventTime": status_raw["endEventTime"],
            "flags": status_raw["sectorFlag"],
            "maxLaps": status_raw["maximumLaps"],
            "session": status_raw["session"],
            "vehicles": standings_raw
        }
    except:
        result = None

    if not result:
        result = {
            "not_running": True
        }
    return result
