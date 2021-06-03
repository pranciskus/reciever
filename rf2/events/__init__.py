LOW_SPEED_THRESHOLD = 50

STATUS_INTERVALS_FOR_LOW_SPEED_HOOK = 5

LAG_DIFFERENCE_THRESHOLD = 80


def get_prop_map(drivers, property):
    result = {}
    for driver in drivers:
        result[driver["driverName"]] = driver[property]

    return result


def get_laps_by_slot(drivers):
    result = {}
    for driver in drivers:
        result[driver["slotid"]] = driver["lapsCompleted"]

    return result