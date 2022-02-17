def onCarCountChange(oldStatus, newStatus, all_hooks):
    old_status_cars = oldStatus.get("vehicles", [])
    new_status_cars = newStatus.get("vehicles", [])
    if len(new_status_cars) != len(old_status_cars):
        for hook in all_hooks:
            hook(old_status_cars, new_status_cars, newStatus)
