+++
title = "xpub"
summary = "An extended public key: a public key plus its chain code, enough to derive all non-hardened child public keys."
category = "Blockchain"
related = ["bip-32", "hardened-derivation", "hd-wallet"]
posts = ["bc-hd-wallets-rust", "bc-exchange-deposits-withdrawals", "bc-capstone"]
+++

A watch-only server can generate fresh deposit addresses from an xpub without holding any private key. It is still sensitive: it links all those addresses together, and with any one leaked non-[hardened](/glossary/hardened-derivation/) child private key it reveals the parent private key.
