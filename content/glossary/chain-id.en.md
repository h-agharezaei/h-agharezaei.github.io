+++
title = "Chain ID"
summary = "A number that identifies one chain and is included in the signed transaction data, so a transaction is valid only there."
category = "Blockchain"
related = ["replay-attack", "account-model"]
posts = ["bc-account-model-nonce", "bc-go-ethereum-client", "bc-bridges-cross-chain"]
+++

According to EIP-155, Ethereum transactions include the chain ID in what is signed, so a transaction from one chain cannot be replayed on another chain that shares the same keys and history.
