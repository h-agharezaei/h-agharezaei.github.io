+++
title = "Merkle root"
summary = "The single hash at the top of a Merkle tree; it commits to every leaf below it."
category = "Blockchain"
related = ["merkle-tree", "inclusion-proof", "block-header"]
posts = ["bc-merkle-trees-proofs"]
+++

A block header stores the Merkle root of its transactions. Changing, adding or reordering any transaction changes the root and therefore the block hash.
