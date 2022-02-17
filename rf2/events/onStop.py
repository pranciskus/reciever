def onStop(oldStatus, newStatus, all_hooks):
    if newStatus.get("not_running") is True and oldStatus.get("not_running") is False:
        for hook in all_hooks:
            hook(newStatus)
