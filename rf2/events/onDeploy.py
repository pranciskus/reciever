def onDeploy(oldStatus, newStatus, all_hooks):
    for hook in all_hooks:
        hook()
