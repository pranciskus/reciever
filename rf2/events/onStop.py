def onStop(oldStatus, newStatus, all_hooks):
    if newStatus["running"] is False and oldStatus["running"] is True:
        for hook in all_hooks:
            hook(newStatus)
