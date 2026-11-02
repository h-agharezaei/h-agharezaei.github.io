+++
title = "Second preimage attack"
summary = "Finding a second input that hashes to the same value as a given input."
category = "Blockchain"
related = ["domain-separation", "merkle-tree"]
posts = ["bc-merkle-trees-proofs"]
+++

Against SHA-256 itself this is not known to be practical. A badly designed Merkle tree allows it anyway: without [domain separation](/glossary/domain-separation/), the 64 bytes behind an inner node can be passed off as a leaf.
