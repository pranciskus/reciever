def onStart(oldStatus, newStatus, all_hooks):
    if "build" not in oldStatus and "build" in newStatus:
        for hook in all_hooks:
            hook()
