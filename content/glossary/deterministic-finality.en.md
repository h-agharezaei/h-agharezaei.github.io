+++
title = "Deterministic finality"
summary = "A block is final as soon as validators holding more than 2/3 of the stake sign a commit for it; it cannot be reverted without a third of the stake signing conflicting votes."
category = "Blockchain"
related = ["probabilistic-finality", "quorum", "equivocation"]
posts = ["bc-proof-of-stake-bft"]
+++

The opposite of [probabilistic finality](/glossary/probabilistic-finality/) in proof of work, where waiting for more confirmations only lowers the risk. If the network splits, BFT protocols stop committing instead of building two histories.
