+++
title = "Light client"
summary = "A client that follows a chain's headers and consensus and checks Merkle proofs, without executing every transaction."
category = "Blockchain"
related = ["bridge", "merkle-tree", "confirmation"]
posts = ["bc-bridges-cross-chain"]
+++

Run inside a contract on another chain, it lets a [bridge](/glossary/bridge/) verify the source chain instead of trusting signers. It is only as safe as the source chain's finality.
