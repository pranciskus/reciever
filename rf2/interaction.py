from rf2.util import get_main_window, get_server_port
from enum import Enum
from time import sleep
from requests import post


class Action(Enum):
    RESTARTWEEKEND = "<< Restart Weekend"
    RESTARTRACE = "< Restart Race"
    NEXTSESSION = "Next Session >"
    NEXTRACE = "Go To Next Race"
    ADDBOT = "Add AI"


def chat(server_config: dict, message: str):
    """
    Sends a chat m essage

    Args:
        server_config: The global configuration for this instance
        message: The message to write (50 chars)
    """
    if len(message) > 50:
        raise Exception("Message to long")

    target_url = "http://localhost:{}/rest/chat".format(get_server_port(server_config))

    try:
        got = post(target_url, data=message)
    except Exception as e:
        print(e)


def do_action(server_config: dict, action: Action):
    dialog = get_main_window(server_config)
    if dialog:
        dialog[action].click()


def kick_player(server_config: dict, name: str):
    dialog = get_main_window(server_config)
    if dialog:
        player_list = dialog.window(best_match="ListBox0:ListBox")

        players = player_list.item_texts()
        for key, value in enumerate(players):
            if name + " (" in value:
                player_list.select(key)
                sleep(0.5)
                break
        dialog["Boot"].click()
