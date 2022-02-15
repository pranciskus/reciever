from rf2.events import get_prop_map
import logging

logger = logging.getLogger(__name__)


def get_pit_status_map(drivers):
    result = {}
    for driver in drivers:
        result[driver["driverName"]] = driver["pitState"]

    return result


def onPitStateChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_status = get_pit_status_map(old_vehicles)
        new_driver_status = get_pit_status_map(new_vehicles)

        for driver, status in new_driver_status.items():
            old_status = (
                old_driver_status[driver] if driver in old_driver_status else None
            )
            if old_status != status:
                for hook in all_hooks:
                    hook(driver, old_status, status, newStatus)


def onGarageToggle(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_status = get_prop_map(old_vehicles, "inGarageStall")
        new_driver_status = get_prop_map(new_vehicles, "inGarageStall")
        pitting_drivers = get_prop_map(new_vehicles, "pitting")

        for driver, status in new_driver_status.items():
            old_status = (
                old_driver_status[driver] if driver in old_driver_status else None
            )
            is_pitting = pitting_drivers[driver] if driver in pitting_drivers else False
            if old_status != status and not is_pitting:
                for hook in all_hooks:
                    hook(driver, old_status, status, newStatus)


def onPittingChange(oldStatus, newStatus, all_hooks):
    if "vehicles" in oldStatus and "vehicles" in newStatus:
        old_vehicles = oldStatus["vehicles"]
        new_vehicles = newStatus["vehicles"]

        old_driver_status = get_prop_map(old_vehicles, "pitting")
        new_driver_status = get_prop_map(new_vehicles, "pitting")
        in_garage_drivers = get_prop_map(new_vehicles, "inGarageStall")

        for driver, status in new_driver_status.items():
            old_status = (
                old_driver_status[driver] if driver in old_driver_status else None
            )
            is_in_garage = (
                in_garage_drivers[driver] if driver in in_garage_drivers else False
            )
            if old_status != status and not is_in_garage:
                for hook in all_hooks:
                    hook(driver, old_status, status, newStatus)
