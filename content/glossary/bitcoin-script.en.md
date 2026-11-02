+++
title = "Bitcoin Script"
summary = "Bitcoin's small stack-based language: each output carries a locking script and the spender supplies the data that unlocks it."
category = "Blockchain"
related = ["utxo", "p2pkh", "stack", "turing-complete"]
posts = ["bc-bitcoin-script-rust"]
+++

A node runs the unlocking data and then the locking script (`scriptPubKey`) on one [stack](/glossary/stack/); the output can be spent only if the result is true. According to the Bitcoin wiki it has no loops, so it is not [Turing-complete](/glossary/turing-complete/). The classic lock is [P2PKH](/glossary/p2pkh/).
