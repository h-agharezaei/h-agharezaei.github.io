+++
title = "Sighash"
summary = "The hash of a transaction that a signature actually covers; it leaves the signatures themselves out."
category = "Blockchain"
related = ["digital-signature", "signature-malleability", "canonical-encoding"]
posts = ["bc-transactions-utxo"]
+++

A signature cannot sign itself, so the signed bytes are the transaction with empty signature fields. Whatever the sighash does not cover can be changed by anyone without breaking the signature.
