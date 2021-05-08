def best_lap(driver, time, team):
    print("New best lap {}: {}".format(driver, time))


def new_lap(driver, laps):
    print("New lap count {}: {}".format(driver, laps))


def on_pos_change(driver, old_pos, new_pos):
    print("New position for {}: {} (was {}) ".format(driver, new_pos, old_pos))


def on_pos_change_yellow(driver, old_pos, new_pos):
    print("New position for {}: {} (was {}) ".format(driver, new_pos, old_pos))


def test_lag(driver, speed, old_speed, location, nearby, team, additional):
    print(
        "Suspected lag for {} v={}, v_old={}, l={}, nearby={}".format(
            driver, speed, old_speed, location, nearby
        )
    )


def add_penalty(driver, old_penalty_count, penalty_count):
    print("A penalty was added for {}. Sum={}".format(driver, penalty_count))


def revoke_penalty(driver, old_penalty_count, penalty_count):
    print("A penalty was removed for {}. Sum={}".format(driver, penalty_count))


def personal_best(driver, old_best, new_best):
    print(
        "A personal best was set: {} old={}, new={}".format(driver, old_best, new_best)
    )


def on_pit_change(driver, old_status, status):
    print(
        "Pit status change for {} is now {}, was {}".format(driver, status, old_status)
    )


def on_garage_toggle(driver, old_status, status):
    if status:
        print("{} is now exiting the garage".format(driver))
    else:
        print("{} returned to the garage".format(driver))


def on_pitting(driver, old_status, status):
    if status:
        print("{} is now pitting".format(driver))
    else:
        print("{} finished pitting".format(driver))


def status_change(driver, old_status, new_status):
    print(
        "Finish status change for {} is now {}, was {}".format(
            driver, new_status, old_status
        )
    )


def on_flag_change(driver, old_flag, new_flag):
    print(
        "Driver {} sees a flag change to {} (was {})".format(driver, new_flag, old_flag)
    )
