import logging

logger = logging.getLogger(__name__)


def get_driver_by_slot(drivers):
    result = {}
    for driver in drivers:
        result[driver["slotID"]] = driver["driverName"]

    return result


def onDriverSwap(oldStatus, newStatus, all_hooks):
    new_vehicles = newStatus["vehicles"]
    old_vehicles = oldStatus["vehicles"]

    if not old_vehicles or not new_vehicles:
        return

    new_drivers = get_driver_by_slot(new_vehicles)
    old_drivers = get_driver_by_slot(old_vehicles)
    for slotId, driver in new_drivers.items():
        if slotId in old_drivers:
            old_driver = old_drivers[slotId]
            new_driver = driver
            if old_driver != new_driver:
                for hook in all_hooks:
                    hook(slotId, old_driver, new_driver, newStatus)
