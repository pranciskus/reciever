def onNewReplay(oldStatus, newStatus, all_hooks):
    if "results" in oldStatus and "results" in newStatus:
        old_results = oldStatus["results"]
        new_results = newStatus["results"]
        if len(old_results) != len(new_results):
            for hook in all_hooks:
                hook(old_results, new_results)
