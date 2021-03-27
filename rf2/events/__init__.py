LOW_SPEED_THRESHOLD = 50


def get_prop_map(drivers, property):
    result = {}
    for driver in drivers:
        result[driver["driverName"]] = driver[property]

    return result