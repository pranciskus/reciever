from rf2.events import get_prop_map


def onDriverPenaltyChange(oldStatus, newStatus, all_hooks):
    old_vehicles = oldStatus.get("vehicles", [])
    new_vehicles = newStatus.get("vehicles", [])

    if not old_vehicles or not new_vehicles:
        return

    old_driver_penalties = get_prop_map(old_vehicles, "penalties")
    new_driver_penalties = get_prop_map(new_vehicles, "penalties")

    for driver, penalty_count in new_driver_penalties.items():
        old_penalty_count = old_driver_penalties.get(driver, 0)
        if old_penalty_count != penalty_count:
            for hook in all_hooks:
                hook(driver, old_penalty_count, penalty_count, newStatus)


def onDriverPenaltyRevoke(oldStatus, newStatus, all_hooks):
    old_vehicles = oldStatus.get("vehicles", [])
    new_vehicles = newStatus.get("vehicles", [])

    if not old_vehicles or not new_vehicles:
        return

    old_driver_penalties = get_prop_map(old_vehicles, "penalties")
    new_driver_penalties = get_prop_map(new_vehicles, "penalties")

    for driver, penalty_count in new_driver_penalties.items():
        old_penalty_count = old_driver_penalties.get(driver, 0)
        if old_penalty_count > penalty_count:
            for hook in all_hooks:
                hook(driver, old_penalty_count, penalty_count, newStatus)


def onDriverPenaltyAdd(oldStatus, newStatus, all_hooks):
    old_vehicles = oldStatus.get("vehicles", [])
    new_vehicles = newStatus.get("vehicles", [])

    if not old_vehicles or not new_vehicles:
        return

    old_driver_penalties = get_prop_map(old_vehicles, "penalties")
    new_driver_penalties = get_prop_map(new_vehicles, "penalties")

    for driver, penalty_count in new_driver_penalties.items():
        old_penalty_count = old_driver_penalties.get(driver, 0)
        if old_penalty_count < penalty_count:
            for hook in all_hooks:
                hook(driver, old_penalty_count, penalty_count, newStatus)
