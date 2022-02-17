def onNewReplay(oldStatus, newStatus, all_hooks):
    if not oldStatus["replays"] or not newStatus["replays"]:
        return
    old_replays = oldStatus["replays"]
    new_replays = newStatus["replays"]
    if len(old_replays) != len(new_replays):
        for hook in all_hooks:
            hook(old_replays, new_replays, newStatus)
