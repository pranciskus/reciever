from os.path import join
from os import listdir


def get_results(server_config: dict) -> list:
    root_path = server_config["server"]["root_path"]
    result_path = join(root_path, "server", "UserData", "Log", "Results")
    return list(filter(lambda f: ".xml" in f, listdir(result_path)))


def get_replays(server_config: dict) -> list:
    root_path = server_config["server"]["root_path"]
    replays_path = join(root_path, "server", "UserData", "Replays")
    return list(filter(lambda f: ".Vcr" in f, listdir(replays_path)))
