LOW_SPEED_THRESHOLD = 50

STATUS_INTERVALS_FOR_LOW_SPEED_HOOK = 5


def get_prop_map(drivers, property):
    result = {}
    for driver in drivers:
        result[driver["driverName"]] = driver[property]

    return result