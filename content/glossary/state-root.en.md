+++
title = "State root"
summary = "A single hash, usually a Merkle root, that commits to an entire state such as all account balances."
category = "Blockchain"
related = ["merkle-root", "merkle-tree", "rollup"]
posts = ["bc-layer2-rollups"]
+++

Changing any balance changes the root, and a [Merkle proof](/glossary/merkle-tree/) can show one balance against it. Rollups post state roots to L1.
