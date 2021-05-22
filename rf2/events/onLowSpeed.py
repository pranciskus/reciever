from math import sqrt
from rf2.events import (
    LOW_SPEED_THRESHOLD,
    STATUS_INTERVALS_FOR_LOW_SPEED_HOOK,
    LAG_DIFFERENCE_THRESHOLD,
)


def get_speed(drivers):
    result = {}
    for driver in drivers:
        if not driver["pitting"] and not driver["inGarageStall"]:
            x = driver["carVelocity"]["x"]
            y = driver["carVelocity"]["y"]
            z = driver["carVelocity"]["z"]
            speed = sqrt(x * x + y * y + z * z) * 3.6
            result[driver["driverName"]] = {
                "speed": speed,
                "lapDistance": driver["lapDistance"],
                "nearby": [],
                "teamName": driver["vehicleName"],
                "additional": {
                    "x": driver["carPosition"]["x"],
                    "y": driver["carPosition"]["y"],
                    "z": driver["carPosition"]["z"],
                },
            }

    for driver_name, infos in result.items():
        # find nearby drivers
        if infos["speed"] < LOW_SPEED_THRESHOLD:
            location = infos["lapDistance"]
            maximum = location + 100
            minimum = location - 200
            to_be_warned = []
            for other_driver, other_driver_infos in result.items():
                other_driver_location = other_driver_infos["lapDistance"]
                if (
                    other_driver_location > minimum
                    and other_driver_location < maximum
                    and driver_name != other_driver
                ):
                    to_be_warned.append(other_driver)
            infos["nearby"] = to_be_warned
    return result


warns = {}
lag_warns = {}


def onLowSpeed(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        new_vehicles = newStatus["vehicles"]

        new_driver_speed = get_speed(new_vehicles)

        for driver, speed in new_driver_speed.items():
            if speed["speed"] < LOW_SPEED_THRESHOLD:
                if driver not in warns:
                    warns[driver] = 0
                warns[driver] = warns[driver] + 1
                if warns[driver] > STATUS_INTERVALS_FOR_LOW_SPEED_HOOK:
                    for hook in all_hooks:
                        hook(
                            driver,
                            speed["speed"],
                            speed["lapDistance"],
                            speed["nearby"],
                            speed["teamName"],
                            speed["additional"],
                            newStatus,
                        )
                    del warns[driver]


def onSuspectedLag(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        new_vehicles = newStatus["vehicles"]
        old_vehicles = oldStatus["vehicles"]

        new_driver_speed = get_speed(new_vehicles)
        old_driver_speed = get_speed(old_vehicles)
        try:
            for driver, speed in new_driver_speed.items():
                old_speed = (
                    old_driver_speed[driver]["speed"]
                    if driver in old_driver_speed
                    else 0
                )
                speed_difference = abs(speed["speed"] - old_speed)
                if speed_difference > LAG_DIFFERENCE_THRESHOLD:
                    if driver not in lag_warns:
                        lag_warns[driver] = 0
                    lag_warns[driver] = lag_warns[driver] + 1
                    if lag_warns[driver] > STATUS_INTERVALS_FOR_LOW_SPEED_HOOK:
                        for hook in all_hooks:
                            hook(
                                driver,
                                speed["speed"],
                                old_speed,
                                speed["lapDistance"],
                                speed["nearby"],
                                speed["teamName"],
                                speed["additional"],
                                newStatus,
                            )
                        del lag_warns[driver]
        except Exception as e:
            import traceback

            print(traceback.print_exc())
            print(e)