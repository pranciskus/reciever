def onTick(oldStatus, newStatus, all_hooks):
    for hook in all_hooks:
        hook(newStatus)
