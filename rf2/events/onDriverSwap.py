def get_driver_by_slot(drivers):
    result = {}
    for driver in drivers:
        result[driver["slotid"]] = driver["driverName"]

    return result


def onDriverSwap(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        new_vehicles = newStatus["vehicles"]
        old_vehicles = newStatus["vehicles"]

        new_drivers = get_driver_by_slot(new_vehicles)
        old_drivers = get_driver_by_slot(old_vehicles)

        for slotId, driver in new_drivers.items():
            old_driver = old_drivers[slotId]
            new_driver = driver
            if old_driver != new_driver:
                for hook in all_hooks:
                    hook(slotId, old_driver, new_driver)