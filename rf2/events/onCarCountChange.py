def onCarCountChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_count = len(oldStatus["vehicles"])
        new_count = len(newStatus["vehicles"])
        if new_count != old_count:
            # execute hooks for this event
            for hook in all_hooks:
                old_status_cars = oldStatus["vehicles"]
                new_status_cars = newStatus["vehicles"]
                hook(old_status_cars, new_status_cars)
