+++
title = "Multisig"
summary = "A wallet that needs signatures from several independent keys (M of N) before funds can move."
category = "Security"
related = ["hot-wallet"]
posts = ["binance-hack-hot-wallet-2026"]
+++

A multisig wallet requires M valid signatures out of N keys, for example 2 of 3, before a transaction is accepted. Stealing one key is not enough. It only helps if the signers check *what* they sign independently; if every signer trusts the same compromised interface or service, the attacker still gets M signatures. MPC (multi-party computation) achieves a similar split of authority without a multisig contract on chain.
