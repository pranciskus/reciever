from rf2.events import get_prop_map


def onPositionChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_pos = get_prop_map(old_vehicles, "position")
        new_driver_pos = get_prop_map(new_vehicles, "position")

        for driver, new_pos in new_driver_pos.items():
            old_pos = old_driver_pos[driver] if driver in old_driver_pos else 0
            if old_pos != new_pos:
                for hook in all_hooks:
                    hook(driver, old_pos, new_pos)


def onUnderYellowPositionChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_pos = get_prop_map(old_vehicles, "position")
        new_driver_pos = get_prop_map(new_vehicles, "position")
        new_driver_yellow = get_prop_map(new_vehicles, "underYellow")

        for driver, new_pos in new_driver_pos.items():
            old_pos = old_driver_pos[driver] if driver in old_driver_pos else 0
            under_yellow = (
                new_driver_yellow[driver] if driver in new_driver_yellow else False
            )
            if old_pos != 0:
                if old_pos != new_pos and under_yellow:
                    for hook in all_hooks:
                        hook(driver, old_pos, new_pos)