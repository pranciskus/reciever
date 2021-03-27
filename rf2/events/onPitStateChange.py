def get_pit_status_map(drivers):
    result = {}
    for driver in drivers:
        result[driver["driverName"]] = driver["pitState"]

    return result


def onPitStateChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_status = get_pit_status_map(old_vehicles)
        new_driver_status = get_pit_status_map(new_vehicles)

        for driver, status in new_driver_status.items():
            old_status = (
                old_driver_status[driver] if driver in old_driver_status else None
            )
            if old_status != status:
                for hook in all_hooks:
                    hook(driver, old_status, status)
