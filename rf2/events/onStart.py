def onStart(oldStatus, newStatus, all_hooks):
    if "not_running" in oldStatus and "not_running" not in newStatus:
        for hook in all_hooks:
            hook()
