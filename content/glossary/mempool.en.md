+++
title = "Mempool"
summary = "A node's pool of valid transactions that are not in a block yet."
category = "Blockchain"
related = ["fee-rate", "block-template", "replace-by-fee"]
posts = ["bc-mempool-fees"]
+++

Every node keeps its own mempool, so there is no single global one. What it accepts (minimum fee rate, size limit, replacement rules) is local policy, not consensus; miners build blocks from it.
