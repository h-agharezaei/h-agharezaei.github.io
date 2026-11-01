+++
title = "Block template"
summary = "The candidate block a miner builds from the mempool before searching for a valid nonce."
category = "Blockchain"
related = ["mempool", "fee-rate", "child-pays-for-parent"]
posts = ["bc-mempool-fees"]
+++

Choosing transactions under a size limit to maximize fees is a knapsack problem; nodes use a greedy approximation ordered by fee rate, with parents always placed before their children.
