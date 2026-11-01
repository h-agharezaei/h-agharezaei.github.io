+++
title = "Fork-choice rule"
summary = "The rule a node uses to pick the active chain among competing branches; in proof of work, most chainwork wins."
category = "Blockchain"
related = ["chainwork", "chain-reorganization", "stale-block"]
posts = ["bc-forks-reorgs", "bc-proof-of-stake-bft"]
+++

Nodes may see blocks in different orders, but if they all apply the same rule to the same set of blocks, they converge on the same chain. Choosing by block count instead of work lets cheap low-difficulty branches win.
