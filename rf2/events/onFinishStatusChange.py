from rf2.events import get_prop_map


def onFinishStatusChange(oldStatus, newStatus, all_hooks):
    new_vehicles = newStatus["vehicles"]
    old_vehicles = oldStatus["vehicles"]

    if not old_vehicles or not new_vehicles:
        return

    old_driver_status = get_prop_map(old_vehicles, "finishStatus")
    new_driver_status = get_prop_map(new_vehicles, "finishStatus")

    for driver, status in new_driver_status.items():
        old_status = old_driver_status.get(driver)
        if old_status != status:
            for hook in all_hooks:
                hook(driver, old_status, status, newStatus)
