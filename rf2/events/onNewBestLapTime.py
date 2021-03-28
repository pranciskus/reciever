overall_best_lap = None
overall_best_time = None


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
