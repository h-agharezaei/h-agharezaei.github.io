+++
title = "MPC"
summary = "Multi-party computation: several parties compute a result together, for wallets a signature, without any one of them holding the whole key."
category = "Security"
related = ["key-custody", "multisig"]
posts = ["bc-capstone"]
+++

In MPC wallets the key exists only as shares held by different parties or machines; a threshold of them runs a protocol that produces one ordinary signature. Unlike [multisig](/glossary/multisig/), the chain sees a single key, so the threshold is enforced off-chain.
