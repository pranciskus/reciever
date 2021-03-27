from rf2.events import get_prop_map


def onFinishStatusChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_status = get_prop_map(old_vehicles, "finishStatus")
        new_driver_status = get_prop_map(new_vehicles, "finishStatus")

        for driver, status in new_driver_status.items():
            old_status = (
                old_driver_status[driver] if driver in old_driver_status else None
            )
            if old_status != status:
                for hook in all_hooks:
                    hook(driver, old_status, status)
