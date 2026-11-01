+++
title = "Chain reorganization (reorg)"
summary = "Switching the active chain to a heavier branch: disconnect blocks back to the common ancestor, then connect the new ones."
category = "Blockchain"
related = ["fork-choice-rule", "stale-block", "probabilistic-finality"]
posts = ["bc-forks-reorgs", "bc-event-indexer-go"]
+++

Disconnecting needs undo data (or a replay) to restore the state. Transactions of the disconnected blocks that are not in the new branch become unconfirmed again; some may now be invalid because the new branch spent the same outputs.
