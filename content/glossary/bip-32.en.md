+++
title = "BIP-32"
summary = "The standard for deriving a tree of child keys from a master key and a chain code with HMAC-SHA512."
category = "Blockchain"
related = ["hd-wallet", "xpub", "hardened-derivation", "bip-44"]
posts = ["bc-hd-wallets-rust"]
+++

The master key and the 32-byte chain code are the two halves of HMAC-SHA512("Bitcoin seed", seed). Each child is HMAC-SHA512(chain code, parent key data || index): the left half tweaks the parent key, the right half is the child's chain code.
