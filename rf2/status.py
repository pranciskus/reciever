from pathlib import Path
from os.path import join, isfile, exists
from requests import get
from requests.exceptions import RequestException
from json import JSONDecodeError
from rf2.util import get_server_port
import logging
from os import listdir

logger = logging.getLogger(__name__)


ROOT_PATH = Path(__file__).parent.parent.absolute()
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

SERVER_VERSION = None
if exists(VERSION_TXT_PATH):
    with open(VERSION_TXT_PATH, "r") as f:
        SERVER_VERSION = f.readlines()[0].strip()


def get_server_mod(server_config: dict) -> dict:
    target_url = "http://localhost:{}".format(get_server_port(server_config))
    try:
        mod_content = get(target_url + "/rest/race/car").json()
        return mod_content
    except Exception as e:
        logger.warning(e)
        return None


# TODO: is alive ping check is necessary - too many calls when the server is down
# TODO: refactor this for better performance - asyncio?
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

    is_unlocked = isfile(UNLOCK_PATH)

    session_id = None

    if exists(SESSION_ID_PATH):
        with open(SESSION_ID_PATH, "r") as file:
            session_id = file.read()

    result = None

    status_raw = {}
    standings_raw = {}
    waypoints = {}
    session_info_raw = {}

    try:
        status_raw = get(target_url + "/rest/watch/sessionInfo").json()
        standings_raw = get(target_url + "/rest/watch/standings").json()
        waypoints = get(target_url + "/navigation/state").json()
        session_info_raw = get(target_url + "/rest/sessions").json()

        # Note: on server start and session change some fields get populated with a delay
        # Trying to get all available data, another option -> implement some caching and have update logic

        result = {
            "track": status_raw.get("trackName"),
            "name": status_raw.get("serverName"),
            "startEventTime": status_raw.get("startEventTime"),
            "currentEventTime": status_raw.get("currentEventTime"),
            "endEventTime": status_raw.get("endEventTime"),
            "flags": status_raw.get("sectorFlag"),
            "maxLaps": status_raw.get("maximumLaps"),
            "session": status_raw.get("session"),
            "vehicles": standings_raw,
            "keys": is_unlocked,
            "build": SERVER_VERSION,
            "release": RECIEVER_RELEASE,
            "session_id": session_id,
            "weather": {
                "ambient": status_raw.get("ambientTemp"),
                "track": status_raw.get("trackTemp"),
                "rain": {
                    "min": status_raw.get("minPathWetness"),
                    "avg": status_raw.get("averagePathWetness"),
                    "max": status_raw.get("maxPathWetness"),
                    "raining": status_raw.get("raining"),
                    "dark_cloud": status_raw.get("darkCloud"),
                },
            },
            "waypoints": waypoints,
            "race_time": session_info_raw.get("SESSSET_race_time", {}).get(
                "currentValue", 0
            )
            * 60,
            "time_completion": status_raw.get("raceCompletion", {}).get(
                "timeCompletion"
            ),
        }

    # FIXME: if server isn't running this logic shouldn't be running
    except RequestException as e:
        logging.warning(e)
        result = None  # do nothing, if the server is not running
    except JSONDecodeError as e:
        logging.warning(e)
        result = None  # do nothing, if the server is not running
    except Exception as e:
        logger.error(e, exc_info=1)
        result = None

    if not result:
        result = {
            "not_running": True,
            "keys": is_unlocked,
            "release": RECIEVER_RELEASE,
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

    return result
