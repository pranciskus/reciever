from hooks.on_start import ping_masterserver

HOOKS = {}


def register(event, hooks, func):
    if event not in hooks:
        hooks[event] = []
    hooks[event].append(func)
    print("Registered hook {} for event {}".format(func.__name__, event))


register("onStart", HOOKS, ping_masterserver)