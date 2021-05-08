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
