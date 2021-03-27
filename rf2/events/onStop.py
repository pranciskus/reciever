def onStop(oldStatus, newStatus, all_hooks):
    if "not_running" in newStatus and "not_running" not in oldStatus:
        for hook in all_hooks:
            hook()
