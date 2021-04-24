from reciever import get_server_config
from requests import post
from json import dumps
from rf2.util import get_public_sim_server_port

MASTERSERVER = "http://localhost:5001"


def ping_masterserver():
    conf = get_server_config()
    all_settings = conf["mod"]
    name = "Unnamed server"
    try:
        name = all_settings["server"]["overwrites"]["Multiplayer.JSON"][
            "Multiplayer Server Options"
        ]["Default Game Name"]
    except Exception as e:
        print(e)
    port = get_public_sim_server_port(conf)
    track = all_settings["track"] if "track" in all_settings else []
    cars = all_settings["cars"] if "cars" in all_settings else []
    mod = all_settings["mod"] if "mod" in all_settings else None
    response = {"name": name, "port": port, "track": track, "cars": cars, "mod": mod}
    try:
        got = post(MASTERSERVER + "/ping", data={"server": dumps(response)})
        if got.status_code == 200:
            print("Successfully greeted {}".format(MASTERSERVER))
        else:
            print("Failure while contacting {}".format(MASTERSERVER))
    except Exception as e:
        print(e)