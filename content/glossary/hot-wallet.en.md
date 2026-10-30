+++
title = "Hot wallet"
summary = "A crypto wallet whose signing keys are online so withdrawals can be signed automatically."
category = "Security"
related = ["multisig", "blast-radius", "least-privilege"]
posts = ["binance-hack-hot-wallet-2026"]
+++

A hot wallet keeps its signing capability connected to the network so an exchange can process withdrawals without a human. That makes it fast, and also the part of the system an attacker aims for. Exchanges usually keep only a small share of funds hot and the rest in cold storage, offline. Whoever can *ask* the hot wallet to sign is as dangerous as whoever holds its key.
