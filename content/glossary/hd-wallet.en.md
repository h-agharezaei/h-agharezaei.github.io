+++
title = "HD wallet"
summary = "A wallet that derives a whole tree of keys from one seed, so one backup covers every address."
category = "Blockchain"
related = ["bip-32", "bip-39", "bip-44", "xpub"]
posts = ["bc-hd-wallets-rust"]
+++

Hierarchical deterministic: keys are computed from a seed and a path, not stored one by one. The rules come from [BIP-32](/glossary/bip-32/), the backup words from [BIP-39](/glossary/bip-39/) and the standard paths from [BIP-44](/glossary/bip-44/).
