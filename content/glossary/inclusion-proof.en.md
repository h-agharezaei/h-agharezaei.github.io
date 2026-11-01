+++
title = "Inclusion proof"
summary = "The sibling hashes on the path from one leaf to the root, proving that leaf is in a Merkle tree."
category = "Blockchain"
related = ["merkle-tree", "merkle-root", "spv"]
posts = ["bc-merkle-trees-proofs"]
+++

The verifier rehashes upward from the leaf and compares with a root it already trusts. The proof has about log2(n) hashes: 20 for a million leaves.
