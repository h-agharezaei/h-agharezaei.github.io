+++
title = "Replay attack"
summary = "Sending a valid, signed message again so it takes effect twice, or on a system it was not meant for."
category = "Blockchain"
related = ["nonce", "chain-id", "account-model"]
posts = ["bc-account-model-nonce"]
+++

The signature stays valid, so the receiver needs state to tell old from new: a nonce or sequence number, an expiry, or a context such as a chain ID inside the signed data.
