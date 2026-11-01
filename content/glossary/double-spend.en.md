+++
title = "Double spend"
summary = "Spending the same coin twice; the core problem a blockchain ledger has to prevent."
category = "Blockchain"
related = ["utxo", "consensus"]
posts = ["bc-transactions-utxo", "bc-account-model-nonce", "bc-forks-reorgs"]
+++

With digital money nothing stops you from signing two payments of the same coin. In the UTXO model the rule is that an output can be an input only once; the network then has to agree on which of the two payments came first.
