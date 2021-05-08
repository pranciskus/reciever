from rf2.events import get_prop_map


def onDriverPenaltyChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_penalties = get_prop_map(old_vehicles, "penalties")
        new_driver_penalties = get_prop_map(new_vehicles, "penalties")

        for driver, penalty_count in new_driver_penalties.items():
            old_penalty_count = (
                old_driver_penalties[driver] if driver in old_driver_penalties else 0
            )
            if old_penalty_count != penalty_count:
                for hook in all_hooks:
                    hook(driver, old_penalty_count, penalty_count)


def onDriverPenaltyRevoke(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_penalties = get_prop_map(old_vehicles, "penalties")
        new_driver_penalties = get_prop_map(new_vehicles, "penalties")

        for driver, penalty_count in new_driver_penalties.items():
            old_penalty_count = (
                old_driver_penalties[driver] if driver in old_driver_penalties else 0
            )
            if old_penalty_count > penalty_count:
                for hook in all_hooks:
                    hook(driver, old_penalty_count, penalty_count)


def onDriverPenaltyAdd(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_penalties = get_prop_map(old_vehicles, "penalties")
        new_driver_penalties = get_prop_map(new_vehicles, "penalties")

        for driver, penalty_count in new_driver_penalties.items():
            old_penalty_count = (
                old_driver_penalties[driver] if driver in old_driver_penalties else 0
            )
            if old_penalty_count < penalty_count:
                for hook in all_hooks:
                    hook(driver, old_penalty_count, penalty_count)