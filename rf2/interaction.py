from rf2.util import get_main_window
from enum import Enum
from time import sleep


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
    dialog = get_main_window(server_config)
    dialog["Chat:Edit"].type_keys(message.replace(" ", "{SPACE}") + "{ENTER}")


def do_action(server_config: dict, action: Action):
    dialog = get_main_window(server_config)
    dialog[action].click()


def kick_player(server_config: dict, name: str):
    dialog = get_main_window(server_config)
    player_list = dialog.window(
        best_match='ListBox0:ListBox')

    players = player_list.item_texts()
    for key, value in enumerate(players):
        if name + " (" in value:
            player_list.select(key)
            sleep(0.5)
            break
    dialog["Boot"].click()
