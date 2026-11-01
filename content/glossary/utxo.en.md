+++
title = "UTXO"
summary = "Unspent transaction output: a coin that an earlier transaction created and nobody has spent yet."
category = "Blockchain"
related = ["double-spend", "coinbase-transaction", "account-model"]
posts = ["bc-transactions-utxo", "bc-account-model-nonce", "bc-bitcoin-script-rust"]
+++

In the UTXO model (Bitcoin) the ledger state is the set of unspent outputs. A transaction consumes whole outputs as inputs and creates new ones; a balance is the sum of the outputs a key can spend.
