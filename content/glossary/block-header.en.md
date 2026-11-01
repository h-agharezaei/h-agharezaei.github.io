+++
title = "Block header"
summary = "The small, fixed-size part of a block that is hashed to give the block its id."
category = "Blockchain"
related = ["genesis-block", "merkle-root", "hash-chain"]
posts = ["bc-hashes-blocks-chain"]
+++

It holds the previous block's hash and a commitment to the block's contents, such as a [Merkle root](/glossary/merkle-root/). Hashing only the header keeps the id cheap to compute and lets light clients keep headers without the transactions.
