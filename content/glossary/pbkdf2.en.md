+++
title = "PBKDF2"
summary = "A key derivation function that repeats an HMAC many times over a password and a salt to make guessing slow."
category = "Blockchain"
related = ["key-derivation-function", "hmac", "salt", "bip-39"]
posts = ["bc-hd-wallets-rust"]
+++

Older and simpler than scrypt or Argon2, and not memory-hard. [BIP-39](/glossary/bip-39/) uses it with HMAC-SHA512 and 2048 rounds to turn a mnemonic into a seed.
