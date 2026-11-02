+++
title = "Relayer"
summary = "An off-chain service that watches one chain and submits messages, often signed, to another."
category = "Blockchain"
related = ["bridge", "multisig", "ecrecover"]
posts = ["bc-bridges-cross-chain"]
+++

If the destination trusts relayer signatures (M of N), the relayer keys are the bridge's security: stealing M of them is enough to forge messages.
