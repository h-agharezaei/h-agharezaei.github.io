+++
title = "Proof of work"
summary = "A block is valid only if its header hash is below a target, so making one costs many hash attempts while checking it costs one."
category = "Blockchain"
related = ["mining", "difficulty-target", "chainwork", "sybil-attack", "consensus"]
posts = ["bc-proof-of-work-mining", "bc-p2p-gossip"]
+++

Proof of work turns block production into a lottery weighted by computation. Miners change a nonce until the header hash meets the [difficulty target](/glossary/difficulty-target/); every node verifies the result with a single hash. Rewriting history means redoing all the work since that point.
