+++
title = "Rollup"
summary = "A Layer 2 that executes transactions off-chain and posts their data plus a state commitment to an L1 contract."
category = "Blockchain"
related = ["layer-2", "sequencer", "state-root", "data-availability"]
posts = ["bc-layer2-rollups"]
+++

Because the data is on L1, anyone can rebuild the state. The L1 contract decides whether a new [state root](/glossary/state-root/) is accepted: after a challenge window ([optimistic](/glossary/optimistic-rollup/)) or after verifying a proof ([ZK](/glossary/zk-rollup/)).
