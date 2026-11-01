+++
title = "Deposit address"
summary = "A blockchain address an exchange assigns to one user, so an incoming transfer to it can be credited to that user."
category = "Blockchain"
related = ["xpub", "hd-wallet", "sweeping"]
posts = ["bc-exchange-deposits-withdrawals", "bc-capstone"]
+++

Exchanges usually derive one address per user from an [xpub](/glossary/xpub/), so the deposit service needs no private key. A watcher matches incoming transfers by their `to` address; the funds are later [swept](/glossary/sweeping/) to the exchange's own wallets.
