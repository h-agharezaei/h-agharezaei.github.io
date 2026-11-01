+++
title = "Child pays for parent (CPFP)"
summary = "Speeding up a low-fee transaction by spending its output in a child that pays a high fee."
category = "Blockchain"
related = ["fee-rate", "block-template", "mempool"]
posts = ["bc-mempool-fees"]
+++

A child is only valid after its parent, so a miner that wants the child's fee must include both. Selection by ancestor package fee rate (the transaction plus its unconfirmed ancestors) makes this work. Unlike RBF, the receiver can do it too.
