def onNewResult(oldStatus, newStatus, all_hooks):
    if "replays" in oldStatus and "replays" in newStatus:
        old_replays = oldStatus["replays"]
        new_replays = newStatus["replays"]
        if len(old_replays) != len(new_replays):
            for hook in all_hooks:
                hook(old_replays, new_replays)
