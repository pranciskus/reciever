from time import time

TARGET_SERVER = "http://localhost:8000/addmessage/cffhddcfgahchafbhifg"

from json import dumps
from requests import post
from threading import Thread


def poll_server_async(event):
    if TARGET_SERVER:
        print("polling with ", event)
        got = post(TARGET_SERVER, json=event)
        print(got)


def poll_server(event):
    background_thread = Thread(target=poll_server_async, args=(event,), daemon=True)
    background_thread.start()


def best_lap(driver, time, team):
    print("New best lap {}: {}".format(driver, time))


def new_lap(driver, laps):
    print("New lap count {}: {}".format(driver, laps))
    poll_server({"driver": driver, "laps": laps, "type": "LC"})


def on_pos_change(driver, old_pos, new_pos):
    print("New position for {}: {} (was {}) ".format(driver, new_pos, old_pos))
    poll_server({"driver": driver, "old_pos": old_pos, "new_pos": new_pos, "type": "P"})


def on_pos_change_yellow(driver, old_pos, new_pos):
    print("New position for {}: {} (was {}) ".format(driver, new_pos, old_pos))
    poll_server(
        {"driver": driver, "old_pos": old_pos, "new_post": new_pos, "type": "PY"}
    )


def test_lag(driver, speed, old_speed, location, nearby, team, additional):
    print(
        "Suspected lag for {} v={}, v_old={}, l={}, nearby={}".format(
            driver, speed, old_speed, location, nearby
        )
    )
    poll_server(
        {
            "driver": driver,
            "speed": speed,
            "old_speed": old_speed,
            "location": location,
            "nearby": nearby,
            "team": team,
            "type": "L",
        }
    )


def add_penalty(driver, old_penalty_count, penalty_count):
    print("A penalty was added for {}. Sum={}".format(driver, penalty_count))
    poll_server({"sum": penalty_count, "driver": driver, "type": "P+"})


def revoke_penalty(driver, old_penalty_count, penalty_count):
    print("A penalty was removed for {}. Sum={}".format(driver, penalty_count))
    poll_server({"sum": penalty_count, "driver": driver, "type": "P-"})


def personal_best(driver, old_best, new_best):
    print(
        "A personal best was set: {} old={}, new={}".format(driver, old_best, new_best)
    )
    poll_server(
        {"new_best": new_best, "old_best": old_best, "driver": driver, "type": "PB"}
    )


def on_pit_change(driver, old_status, status):
    print(
        "Pit status change for {} is now {}, was {}".format(driver, status, old_status)
    )
    if status != "REQUEST":  # request is a bit too leaky for the public
        poll_server(
            {"old_status": old_status, "status": status, "driver": driver, "type": "PS"}
        )


def on_garage_toggle(driver, old_status, status):
    if status:
        print("{} is now exiting the garage".format(driver))
        poll_server(
            {
                "old_status": old_status,
                "status": status,
                "driver": driver,
                "type": "GO",
            }
        )
    else:
        print("{} returned to the garage".format(driver))
        poll_server(
            {
                "old_status": old_status,
                "status": status,
                "driver": driver,
                "type": "GI",
            }
        )


pit_times = {}


def on_pitting(driver, old_status, status):
    if status:
        pit_times[driver] = time()
        print("{} is now pitting".format(driver))
        poll_server(
            {
                "driver": driver,
                "type": "PSS",
            }
        )

    else:
        try:
            start_time = pit_times[driver] if driver in pit_times else 0
            if start_time > 0:
                duration = time() - start_time
                print(
                    "{} finished pitting. Pit took {} seconds.".format(driver, duration)
                )
                poll_server(
                    {
                        "driver": driver,
                        "type": "PSE",
                    }
                )
            else:
                print("{} finished pitting".format(driver))
                poll_server(
                    {
                        "driver": driver,
                        "type": "PSE",
                    }
                )
        except:
            import traceback

            print(traceback.print_exc())


def status_change(driver, old_status, new_status):
    print(
        "Finish status change for {} is now {}, was {}".format(
            driver, new_status, old_status
        )
    )
    poll_server(
        {
            "driver": driver,
            "old_status": old_status,
            "status": new_status,
            "type": "S",
        }
    )


def on_flag_change(driver, old_flag, new_flag):
    print(
        "Driver {} sees a flag change to {} (was {})".format(driver, new_flag, old_flag)
    )
