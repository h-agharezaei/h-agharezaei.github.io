+++
title = "Domain separation"
summary = "Prefixing or tagging hash inputs by purpose, so a hash made for one role cannot be reused in another."
category = "Blockchain"
related = ["second-preimage-attack", "merkle-tree"]
posts = ["bc-merkle-trees-proofs"]
+++

RFC 6962 hashes Merkle leaves as SHA-256(0x00 || data) and inner nodes as SHA-256(0x01 || left || right).
