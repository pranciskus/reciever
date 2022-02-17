def onSessionChange(oldStatus, newStatus, all_hooks):
    old_session = oldStatus["session"]
    new_session = newStatus["session"]

    if old_session != new_session:
        for hook in all_hooks:
            hook(old_session, new_session, newStatus)
