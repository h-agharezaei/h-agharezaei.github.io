+++
title = "AEAD"
summary = "Authenticated encryption with associated data: one operation that gives confidentiality and tamper detection."
category = "Security"
related = ["aes-gcm", "nonce"]
posts = ["sec-crypto-mistakes"]
+++

AES-GCM and ChaCha20-Poly1305 are AEAD constructions. Opening a modified ciphertext fails with an error instead of returning garbage.
