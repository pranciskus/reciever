def get_driver_by_slot(drivers):
    result = {}
    for driver in drivers:
        result[driver["slotid"]] = driver["driverName"]

    return result


def get_steamid_by_slot(drivers):
    result = {}
    for driver in drivers:
        result[driver["slotid"]] = driver["steamID"]

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


def onSteamIdChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        new_vehicles = newStatus["vehicles"]
        old_vehicles = newStatus["vehicles"]

        new_drivers = get_steamid_by_slot(new_vehicles)
        old_drivers = get_steamid_by_slot(old_vehicles)

        for slotId, new_id in new_drivers.items():
            old_id = old_drivers[slotId]
            if old_id != new_id:
                for hook in all_hooks:
                    hook(slotId, old_id, new_id)
