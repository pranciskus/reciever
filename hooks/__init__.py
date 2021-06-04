from hooks.basehooks import (
    best_lap,
    new_lap,
    on_pos_change,
    test_lag,
    on_pos_change_yellow,
    revoke_penalty,
    add_penalty,
    personal_best,
    on_pit_change,
    status_change,
    on_flag_change,
    on_garage_toggle,
    on_pitting,
    on_tick,
    on_stop,
    on_deploy,
)

HOOKS = {}


def register(event, hooks, func):
    if event not in hooks:
        hooks[event] = []
    hooks[event].append(func)
    print("Registered hook {} for event {}".format(func.__name__, event))


register("onNewBestLapTime", HOOKS, best_lap)
register("onLapCompleted", HOOKS, new_lap)
register("onPositionChange", HOOKS, on_pos_change)
register("onSuspectedLag", HOOKS, test_lag)
register("onUnderYellowPositionChange", HOOKS, on_pos_change_yellow)
register("onDriverPenaltyRevoke", HOOKS, revoke_penalty)
register("onDriverPenaltyAdd", HOOKS, add_penalty)
register("onNewPersonalBest", HOOKS, personal_best)
register("onPitStateChange", HOOKS, on_pit_change)
register("onFinishStatusChange", HOOKS, status_change)
register("onShownFlagChange", HOOKS, on_flag_change)
register("onGarageToggle", HOOKS, on_garage_toggle)
register("onPittingChange", HOOKS, on_pitting)
register("onTick", HOOKS, on_tick)
register("onStop", HOOKS, on_stop)
register("onDeploy", HOOKS, on_deploy)