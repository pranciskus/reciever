import re
from os.path import join, isfile
from time import time
from requests import get
from json import load
from rf2.util import get_server_port


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
            "vehicles": standings_raw,
            "keys": is_unlocked,
        }
    except:
        result = None

    if not result:
        result = {"not_running": True, "keys": is_unlocked}
    return result
