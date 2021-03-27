def get_penalty_map(drivers):
    result = {}
    for driver in drivers:
        result[driver["driverName"]] = driver["penalties"]

    return result


def onDriverPenaltyChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_penalties = get_penalty_map(old_vehicles)
        new_driver_penalties = get_penalty_map(new_vehicles)

        for driver, penalty_count in new_driver_penalties.items():
            old_penalty_count = (
                old_driver_penalties[driver] if driver in old_driver_penalties else 0
            )
            if old_penalty_count != penalty_count:
                for hook in all_hooks:
                    hook(driver, old_penalty_count, penalty_count)
