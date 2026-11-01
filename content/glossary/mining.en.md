+++
title = "Mining"
summary = "Searching for a block header whose hash meets the difficulty target by trying nonce after nonce."
category = "Blockchain"
related = ["proof-of-work", "nonce", "difficulty-target"]
posts = ["bc-proof-of-work-mining"]
+++

A miner builds a candidate block, then hashes its header with nonce 0, 1, 2, ... until the hash is small enough. There is no shortcut, so the expected number of tries is fixed by the difficulty. The winner gets the block reward and fees through the coinbase transaction.
