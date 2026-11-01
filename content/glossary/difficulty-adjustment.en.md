+++
title = "Difficulty adjustment"
summary = "Recomputing the difficulty every N blocks from how long they took, so blocks keep coming at the target rate."
category = "Blockchain"
related = ["difficulty-target", "proof-of-work"]
posts = ["bc-proof-of-work-mining"]
+++

When hash power grows, blocks come faster and the next period gets harder; when it drops, easier. Bitcoin retargets every 2016 blocks and limits each step to a factor of 4. The rule must use exact integer math so every node computes the same value.
