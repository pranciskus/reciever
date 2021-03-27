from math import sqrt
from rf2.events import LOW_SPEED_THRESHOLD


def get_speed(drivers):
    result = {}
    for driver in drivers:
        if not driver["pitting"] and not driver["inGarageStall"]:
            x = driver["carVelocity"]["x"]
            y = driver["carVelocity"]["y"]
            z = driver["carVelocity"]["z"]
            speed = sqrt(x * x + y * y + z * z) * 3.6
            result[driver["driverName"]] = speed

    return result


def onLowSpeed(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        new_vehicles = newStatus["vehicles"]

        new_driver_speed = get_speed(new_vehicles)

        for driver, speed in new_driver_speed.items():
            if speed < LOW_SPEED_THRESHOLD:
                for hook in all_hooks:
                    hook(driver, speed)
