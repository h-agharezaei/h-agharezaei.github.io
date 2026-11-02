+++
title = "Hardened derivation"
summary = "A BIP-32 child derivation that needs the parent private key, so an xpub cannot compute it."
category = "Blockchain"
related = ["bip-32", "xpub"]
posts = ["bc-hd-wallets-rust"]
+++

Indexes from 2^31 up, written with an apostrophe (`0'`). The HMAC input is the parent private key instead of the public key. Besides blocking xpub derivation, it stops a leaked child private key plus the parent [xpub](/glossary/xpub/) from revealing the parent private key.
