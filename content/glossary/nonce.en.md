+++
title = "Nonce"
summary = "A value that must be used only once per key, such as the per-message input of AES-GCM."
category = "Security"
related = ["aes-gcm"]
posts = ["sec-secrets-management"]
+++

In AES-GCM a 12-byte nonce is stored next to the ciphertext. Reusing one with the same key breaks both confidentiality and authenticity. Generate it with `crypto/rand`.
