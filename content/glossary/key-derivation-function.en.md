+++
title = "Key derivation function"
summary = "A function that turns a password or a master secret into uniformly random keys of the needed length."
category = "Security"
related = ["salt", "password-hashing"]
posts = ["sec-crypto-mistakes"]
+++

Slow ones (scrypt, Argon2id) are for passwords; fast ones (HKDF) are for already-strong secrets. A password is never a key by itself.
