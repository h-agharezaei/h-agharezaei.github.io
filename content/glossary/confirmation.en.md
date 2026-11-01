+++
title = "Confirmation"
summary = "The number of blocks on top of (and including) the block that contains a transaction."
category = "Blockchain"
related = ["probabilistic-finality", "chain-reorganization"]
posts = ["bc-forks-reorgs", "bc-event-indexer-go"]
+++

One confirmation means the transaction is in the tip block. Each additional block makes a reorg that removes it less likely, so services wait for a number of confirmations that depends on the chain and the amount.
