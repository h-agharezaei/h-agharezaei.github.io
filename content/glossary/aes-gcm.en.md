+++
title = "AES-GCM"
summary = "An authenticated encryption mode: it hides the data and detects any change to it."
category = "Security"
related = ["nonce"]
posts = ["sec-secrets-management", "sec-crypto-mistakes"]
+++

Go offers it through `cipher.NewGCM`. It needs a unique nonce per message and can bind extra data (AAD), such as a record id, to the ciphertext.
