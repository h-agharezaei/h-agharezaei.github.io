+++
title = "BIP-39"
summary = "The standard that turns random entropy into a list of words (a mnemonic) and the words into a 64-byte seed."
category = "Blockchain"
related = ["hd-wallet", "pbkdf2", "bip-32"]
posts = ["bc-hd-wallets-rust"]
+++

128 to 256 bits of entropy plus a SHA-256 checksum are split into 11-bit chunks, each one a word from a 2048-word list. The seed is [PBKDF2](/glossary/pbkdf2/)-HMAC-SHA512 of the words with the salt "mnemonic" + passphrase, 2048 rounds.
