from rf2.events import get_prop_map


def onShownFlagChange(oldStatus, newStatus, all_hooks):
    new_vehicles = newStatus["vehicles"]
    old_vehicles = oldStatus["vehicles"]

    if not old_vehicles or not new_vehicles:
        return

    old_yellow = get_prop_map(old_vehicles, "underYellow")
    new_yellow = get_prop_map(new_vehicles, "underYellow")

    for driver, yellow in new_yellow.items():
        old_yellow_status = old_yellow[driver] if driver in old_yellow else False
        if yellow != old_yellow_status:
            for hook in all_hooks:
                hook(driver, old_yellow_status, yellow, newStatus)
