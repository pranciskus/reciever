from time import time
from json import dumps
from requests import post
from threading import Thread
from reciever import get_server_config, chat
from re import sub
from os.path import join
from os import linesep


def poll_server_async(event):
    config = get_server_config()
    callback_target = config["mod"]["callback_target"]
    if callback_target is not None:
        try:
            got = post(callback_target, json=event)
        except:
            pass


def poll_server_status_async(status):
    config = get_server_config()
    callback_target = config["mod"]["callback_target"]
    if callback_target is not None:
        secret = config["server"]["auth"]
        pattern = r"/addmessage.*"
        callback_target = sub(pattern, f"/addstatus/{secret}", callback_target)
        try:
            got = post(callback_target, json=status)
        except:
            pass


def publish_logfile():
    config = get_server_config()
    callback_target = config["mod"]["callback_target"]
    if callback_target is not None:
        secret = config["server"]["auth"]
        pattern = r"/addmessage.*"
        log_path = join(config["server"]["root_path"], "reciever.log")
        files = {"log": open(log_path, "rb")}
        callback_target = sub(pattern, f"/addlog/{secret}", callback_target)
        try:
            got = post(callback_target, files=files)
        except:
            pass


def get_slot_by_name(name, all_vehicles):
    for vehicle in all_vehicles["vehicles"]:
        if vehicle["driverName"] == name:
            return vehicle["slotID"]
    return None


def get_prop_by_slot(slot, all_vehicles, propName):
    for vehicle in all_vehicles["vehicles"]:
        if vehicle["slotID"] == slot:
            return vehicle[propName]
    return None


def get_last_lap_time(name, all_vehicles):
    for vehicle in all_vehicles["vehicles"]:
        if vehicle["driverName"] == name:
            return vehicle["lastLapTime"]
    return None


def poll_server(event, sync=False):
    if not sync:
        background_thread = Thread(target=poll_server_async, args=(event,), daemon=True)
        background_thread.start()
    else:
        poll_server_async(event)


def poll_status_server(status):
    background_thread = Thread(
        target=poll_server_status_async, args=(status,), daemon=True
    )
    background_thread.start()


def best_lap(driver, time, team, newStatus):
    print("New best lap {}: {}".format(driver, time))


def new_lap(driver, laps, newStatus):
    print("New lap count {}: {}".format(driver, laps))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    last_lap_time = get_last_lap_time(driver, newStatus)
    poll_server(
        {
            "driver": driver,
            "laps": laps,
            "type": "LC",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
            "last_lap_time": last_lap_time,
        }
    )


def on_pos_change(driver, old_pos, new_pos, newStatus):
    print("New position for {}: {} (was {}) ".format(driver, new_pos, old_pos))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    poll_server(
        {
            "driver": driver,
            "old_pos": old_pos,
            "new_pos": new_pos,
            "type": "P",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def on_pos_change_yellow(driver, old_pos, new_pos, newStatus):
    print("New position for {}: {} (was {}) ".format(driver, new_pos, old_pos))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    poll_server(
        {
            "driver": driver,
            "old_pos": old_pos,
            "new_post": new_pos,
            "type": "PY",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def test_lag(driver, speed, old_speed, location, nearby, team, additional, newStatus):
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
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
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def add_penalty(driver, old_penalty_count, penalty_count, newStatus):
    print("A penalty was added for {}. Sum={}".format(driver, penalty_count))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    slot = get_slot_by_name(driver, newStatus)
    laps = get_prop_by_slot(slot, newStatus, "lapsCompleted")
    poll_server(
        {
            "sum": penalty_count,
            "driver": driver,
            "type": "P+",
            "event_time": event_time,
            "session": session,
            "slot_id": slot,
            "laps": laps,
        }
    )


def revoke_penalty(driver, old_penalty_count, penalty_count, newStatus):
    print("A penalty was removed for {}. Sum={}".format(driver, penalty_count))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    slot = get_slot_by_name(driver, newStatus)
    laps = get_prop_by_slot(slot, newStatus, "lapsCompleted")
    poll_server(
        {
            "sum": penalty_count,
            "driver": driver,
            "type": "P-",
            "event_time": event_time,
            "session": session,
            "slot_id": slot,
            "laps": laps,
        }
    )


def personal_best(driver, old_best, new_best, newStatus):
    print(
        "A personal best was set: {} old={}, new={}".format(driver, old_best, new_best)
    )
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    slot = get_slot_by_name(driver, newStatus)
    laps = get_prop_by_slot(slot, newStatus, "lapsCompleted")
    poll_server(
        {
            "new_best": new_best,
            "old_best": old_best,
            "driver": driver,
            "type": "PB",
            "event_time": event_time,
            "session": session,
            "slot_id": slot,
            "laps": laps,
        }
    )


def on_pit_change(driver, old_status, status, newStatus):
    print(
        "Pit status change for {} is now {}, was {}".format(driver, status, old_status)
    )
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    slot = get_slot_by_name(driver, newStatus)
    laps = get_prop_by_slot(slot, newStatus, "lapsCompleted")
    if status != "REQUEST":  # request is a bit too leaky for the public
        poll_server(
            {
                "old_status": old_status,
                "status": status,
                "driver": driver,
                "type": "PS",
                "event_time": event_time,
                "session": session,
                "slot_id": slot,
                "laps": laps,
            }
        )


def on_garage_toggle(driver, old_status, status, newStatus):
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    slot = get_slot_by_name(driver, newStatus)
    laps = get_prop_by_slot(slot, newStatus, "lapsCompleted")
    if status:
        print("{} is now exiting the garage".format(driver))
        poll_server(
            {
                "old_status": old_status,
                "status": status,
                "driver": driver,
                "type": "GO",
                "event_time": event_time,
                "session": session,
                "slot_id": get_slot_by_name(driver, newStatus),
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
                "event_time": event_time,
                "session": session,
                "slot_id": slot,
                "laps": laps,
            }
        )


pit_times = {}


def on_pitting(driver, old_status, status, newStatus):
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]

    slot = get_slot_by_name(driver, newStatus)
    laps = get_prop_by_slot(slot, newStatus, "lapsCompleted")
    if status:
        pit_times[driver] = time()
        print("{} is now pitting".format(driver))
        poll_server(
            {
                "driver": driver,
                "type": "PSS",
                "event_time": event_time,
                "session": session,
                "slot_id": slot,
                "laps": laps,
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
                        "event_time": event_time,
                        "session": session,
                        "slot_id": slot,
                        "laps": laps,
                    }
                )
            else:
                print("{} finished pitting".format(driver))
                poll_server(
                    {
                        "driver": driver,
                        "type": "PSE",
                        "event_time": event_time,
                        "session": session,
                        "slot_id": slot,
                        "laps": laps,
                    }
                )
        except:
            import traceback

            print(traceback.print_exc())


def status_change(driver, old_status, new_status, newStatus):
    print(
        "Finish status change for {} is now {}, was {}".format(
            driver, new_status, old_status
        )
    )

    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]

    slot = get_slot_by_name(driver, newStatus)
    laps = get_prop_by_slot(slot, newStatus, "lapsCompleted")
    poll_server(
        {
            "driver": driver,
            "old_status": old_status,
            "status": new_status,
            "type": "S",
            "event_time": event_time,
            "session": session,
            "slot_id": slot,
            "laps": laps,
        }
    )


def on_flag_change(driver, old_flag, new_flag, newStatus):
    print(
        "Driver {} sees a flag change to {} (was {})".format(driver, new_flag, old_flag)
    )


def on_tick(status):
    poll_status_server(status)


def on_stop(status):
    poll_status_server(status)


def on_deploy():
    publish_logfile()


def on_car_count_change(old_status_cars, new_status_cars, newStatus):
    config = get_server_config()
    old_slot_ids = []
    welcome_message = config["mod"]["welcome_message"]

    if welcome_message:
        for old_car in old_status_cars:
            old_slot_ids.append(old_car["slotID"])

        for new_car in new_status_cars:
            slot_id = new_car["slotID"]
            driver_name = new_car["driverName"]
            if slot_id not in old_slot_ids:
                parts = welcome_message.split(linesep)
                for part in parts:
                    message = part.replace("{driver_name}", driver_name)
                    chat(config, part.replace("{driver_name}", driver_name))


def on_low_speed(driver, speed, location, nearby, team, additional, newStatus):

    event_time = newStatus["currentEventTime"]
    slot = get_slot_by_name(driver, newStatus)
    laps = get_prop_by_slot(slot, newStatus, "lapsCompleted")
    print(driver, location)
    session = newStatus["session"]
    poll_server(
        {
            "driver": driver,
            "type": "VL",
            "event_time": event_time,
            "session": session,
            "slot_id": slot,
            "laps": laps,
            "nearby": nearby,
            "speed": speed,
            "location": location,
        }
    )


def on_driver_swap(slotId, old_driver, new_driver, newStatus):
    event_time = newStatus["currentEventTime"]
    slot = get_slot_by_name(new_driver, newStatus)
    laps = get_prop_by_slot(slot, newStatus, "lapsCompleted")

    session = newStatus["session"]
    poll_server(
        {
            "type": "DS",
            "event_time": event_time,
            "session": session,
            "slot_id": slot,
            "laps": laps,
            "old_driver": old_driver,
            "new_driver": new_driver,
        }
    )


def on_state_change(descriptor, args):
    poll_server({"type": "SC", "event": descriptor, "args": args}, True)
