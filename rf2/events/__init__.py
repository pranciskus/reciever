import logging

logger = logging.getLogger(__name__)

LOW_SPEED_THRESHOLD = 50
STATUS_INTERVALS_FOR_LOW_SPEED_HOOK = 5
LAG_DIFFERENCE_THRESHOLD = 80


def get_prop_map(drivers, property):
    result = {}
    for driver_data in drivers:
        if isinstance(driver_data, dict) and "driverName" in driver_data:
            result[driver_data["driverName"]] = driver_data[property]
    return result


def get_laps_by_slot(drivers):
    result = {}
    for driver_data in drivers:
        if isinstance(driver_data, dict) and "slotid" in driver_data:
            result[driver_data["slotid"]] = driver_data["lapsCompleted"]
    return result
