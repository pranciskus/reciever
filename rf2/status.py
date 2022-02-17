from pathlib import Path
from os.path import join, isfile, exists
from requests import get
from requests.exceptions import RequestException
from json import JSONDecodeError
from rf2.util import get_server_port
import logging
from os import listdir

logger = logging.getLogger(__name__)


ROOT_PATH = Path(__file__).parent.parent.parent.absolute()
UNLOCK_PATH = join(ROOT_PATH, "server", "UserData", "ServerUnlock.bin")
RELEASE_FILE_PATH = join(ROOT_PATH, "reciever", "release")
VERSION_TXT_PATH = join(ROOT_PATH, "server", "Core", "Version.txt")
DELPOY_LOCK_PATH = join(ROOT_PATH, "reciever", "deploy.lock")
RESULTS_PATH = join(ROOT_PATH, "server", "UserData", "Log", "Results")
REPLAYS_PATH = join(ROOT_PATH, "server", "UserData", "Replays")
SESSION_ID_PATH = join(ROOT_PATH, "reciever", "session_id.txt")


RECIEVER_RELEASE = None
if exists(RELEASE_FILE_PATH):
    with open(RELEASE_FILE_PATH, "r") as f:
        RECIEVER_RELEASE = f.read()


def get_server_mod(server_config: dict) -> dict:
    target_url = "http://localhost:{}".format(get_server_port(server_config))
    try:
        mod_content = get(target_url + "/rest/race/car").json()
        return mod_content
    except Exception as e:
        logger.warning(e)
        return None


# TODO: we need even faster check
def is_server_up(url):
    try:
        get(url=url, verify=False, timeout=0.5)
        return True
    except Exception as e:
        logger.error(str(e))
        logger.warning(f"rF2 server is not running: {url}")
        return False


def get_server_endpoint_data(url, empty_response):
    try:
        data = get(url, verify=False).json()

        if "error" in data:
            logging.warning(f"rf2 server endpoint {url} error: {data}")
            return empty_response, True

        return data, False

    except RequestException as e:
        logging.warning(e)
        return empty_response, True

    except JSONDecodeError as e:
        logging.warning(e)
        return empty_response, True

    except Exception as e:
        logger.error(e, exc_info=1)
        return empty_response, True


# TODO: refactor this for better performance - asyncio?
# NOTE: on server start and session change some fields get populated with a delay
# Trying to get all available data, another option -> implement some caching and have update logic
def get_server_live_data(url):
    status, status_error = get_server_endpoint_data(
        url + "/rest/watch/sessionInfo", dict()
    )
    standings, standings_error = get_server_endpoint_data(
        url + "/rest/watch/standings", list()
    )
    waypoints, waypoints_error = get_server_endpoint_data(
        url + "/navigation/state", dict()
    )
    session, session_error = get_server_endpoint_data(url + "/rest/sessions", dict())

    has_error = any([status_error, standings_error, waypoints_error, session_error])

    result = {
        "skip_polling": has_error,
        "track": status.get("trackName"),
        "name": status.get("serverName"),
        "startEventTime": status.get("startEventTime"),
        "currentEventTime": status.get("currentEventTime"),
        "endEventTime": status.get("endEventTime"),
        "flags": status.get("sectorFlag"),
        "maxLaps": status.get("maximumLaps"),
        "session": status.get("session"),
        "vehicles": standings,
        "weather": {
            "ambient": status.get("ambientTemp"),
            "track": status.get("trackTemp"),
            "rain": {
                "min": status.get("minPathWetness"),
                "avg": status.get("averagePathWetness"),
                "max": status.get("maxPathWetness"),
                "raining": status.get("raining"),
                "dark_cloud": status.get("darkCloud"),
            },
        },
        "waypoints": waypoints,
        "race_time": session.get("SESSSET_race_time", {}).get("currentValue", 0) * 60,
        "time_completion": status.get("raceCompletion", {}).get("timeCompletion"),
    }

    return result


# TODO: diferent outputs for polling and API - e.g. full=True
def get_server_status(server_config: dict) -> dict:
    """
    Get the current server status

    Args:
        server_config: The global configuration for this instance

    Returns:
        A dictionary containing the current server state
    """
    target_url = "http://localhost:{}".format(get_server_port(server_config))

    is_running = is_server_up(target_url)

    SESSION_ID = None
    if exists(SESSION_ID_PATH):
        with open(SESSION_ID_PATH, "r") as file:
            SESSION_ID = file.read()

    SERVER_VERSION = None
    if exists(VERSION_TXT_PATH):
        with open(VERSION_TXT_PATH, "r") as f:
            SERVER_VERSION = f.readlines()[0].strip()

    IS_UNLOCKED = isfile(UNLOCK_PATH)

    result = {
        "not_running": not is_running,
        "keys": IS_UNLOCKED,
        "build": SERVER_VERSION,
        "release": RECIEVER_RELEASE,
        "session_id": SESSION_ID,
    }

    if exists(DELPOY_LOCK_PATH):
        result["in_deploy"] = True

    result["replays"] = (
        list(
            filter(
                lambda x: "tmp" not in x and "apx-keep.txt" not in x,
                listdir(REPLAYS_PATH),
            )
        )
        if exists(REPLAYS_PATH)
        else []
    )

    result["results"] = (
        list(filter(lambda x: "xml" in x, listdir(RESULTS_PATH)))
        if exists(RESULTS_PATH)
        else []
    )

    if is_running:
        live_data = get_server_live_data(target_url)
        result = {**result, **live_data}

    return result
