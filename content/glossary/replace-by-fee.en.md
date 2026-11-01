+++
title = "Replace-by-fee (RBF)"
summary = "Mempool policy that lets a conflicting transaction replace an unconfirmed one if it pays enough more fee."
category = "Blockchain"
related = ["mempool", "fee-rate", "double-spend"]
posts = ["bc-mempool-fees"]
+++

It is the honest way to bump a stuck payment. Bitcoin's rules are in BIP-125 (higher absolute fee, pay for its own relay, a limit on how many transactions are replaced). Until a transaction confirms, a replacement can also redirect the payment, which is why unconfirmed payments are not final.
