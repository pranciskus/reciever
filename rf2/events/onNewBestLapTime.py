overall_best_lap = None
overall_best_time = None
from rf2.events import get_prop_map


def onNewBestLapTime(oldStatus, newStatus, all_hooks):
    global overall_best_lap
    global overall_best_time
    if newStatus["currentEventTime"] < overall_best_time:
        # session was most likely restarted
        overall_best_lap = None
        overall_best_time = None
    if "vehicles" in newStatus:
        new_vehicles = newStatus["vehicles"]
        for vehicle in new_vehicles:
            driver = vehicle["driverName"]
            best_lap = vehicle["bestLapTime"]
            teamName = vehicle["vehicleName"]
            if overall_best_lap is None and best_lap > 0:
                overall_best_lap = best_lap
                overall_best_time = newStatus["currentEventTime"]

            if (
                overall_best_lap is not None
                and best_lap < overall_best_lap
                and best_lap > 0
            ):
                overall_best_lap = best_lap
                overall_best_time = newStatus["currentEventTime"]
                for hook in all_hooks:
                    hook(driver, best_lap, teamName)


def onNewPersonalBest(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        try:
            old_vehicles = oldStatus["vehicles"]
            new_vehicles = newStatus["vehicles"]

            old_driver_best = get_prop_map(old_vehicles, "bestLapTime")
            new_driver_best = get_prop_map(new_vehicles, "bestLapTime")

            for driver, new_best in old_driver_best.items():
                old_best = old_driver_best[driver] if driver in old_driver_best else 0
                # fire the hook either with a regular best or an overall best for this driver.
                if old_best > new_best or new_best > 0 and old_best < 0:
                    for hook in all_hooks:
                        hook(driver, old_best, new_best, newStatus)
        except:
            import traceback

            print(traceback.print_exc())