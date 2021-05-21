from rf2.events import get_prop_map


def onLapCompleted(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_laps = get_prop_map(old_vehicles, "lapsCompleted")
        new_driver_laps = get_prop_map(new_vehicles, "lapsCompleted")

        for driver, laps_completed in new_driver_laps.items():
            old_laps = old_driver_laps[driver] if driver in old_driver_laps else 0
            if laps_completed > 0:
                if old_laps != laps_completed:
                    for hook in all_hooks:
                        hook(driver, laps_completed)