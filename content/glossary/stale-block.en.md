+++
title = "Stale block"
summary = "A valid block that ended up off the active chain because a competing branch had more work."
category = "Blockchain"
related = ["chain-reorganization", "fork-choice-rule"]
posts = ["bc-forks-reorgs"]
+++

Stale blocks are often loosely called orphan blocks. Their coinbase reward disappears with them, and their transactions return to the mempool unless the winning branch already contains or conflicts with them.
