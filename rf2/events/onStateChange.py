def onStateChange(newStatus, infos, all_hooks):
    for hook in all_hooks:
        hook(newStatus, infos)
