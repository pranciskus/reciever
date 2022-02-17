def onCarCountChange(oldStatus, newStatus, all_hooks):
    old_status_cars = oldStatus["vehicles"]
    new_status_cars = newStatus["vehicles"]
    if len(new_status_cars) != len(old_status_cars):
        for hook in all_hooks:
            hook(old_status_cars, new_status_cars, newStatus)
