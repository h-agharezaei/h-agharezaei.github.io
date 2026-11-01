+++
title = "Account model"
summary = "A ledger kept as a balance and a nonce per address, as in Ethereum, instead of a set of unspent outputs."
category = "Blockchain"
related = ["utxo", "nonce", "replay-attack"]
posts = ["bc-account-model-nonce", "bc-evm-internals-rust"]
+++

A transfer subtracts from the sender and adds to the receiver. Because a valid signed transfer could be submitted again, each sender has a nonce that every transaction must match.
