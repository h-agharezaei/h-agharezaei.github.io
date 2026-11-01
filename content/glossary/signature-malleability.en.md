+++
title = "Signature malleability"
summary = "A valid signature can be changed into another valid signature for the same message without the private key."
category = "Blockchain"
related = ["ecdsa"]
posts = ["bc-keys-ecdsa-addresses", "bc-transactions-utxo"]
+++

In [ECDSA](/glossary/ecdsa/), (r, s) and (r, n − s) both verify. According to their specs, Ethereum transactions (EIP-2) reject the high S value and Bitcoin Core's relay policy does too, so each signature has one form.
