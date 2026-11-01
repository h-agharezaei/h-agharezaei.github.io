+++
title = "Chainwork"
summary = "The total expected number of hashes behind a chain tip: the sum of each block's work."
category = "Blockchain"
related = ["proof-of-work", "fork-choice-rule", "difficulty-target"]
posts = ["bc-proof-of-work-mining", "bc-forks-reorgs"]
+++

A block at difficulty d is worth about 2^d hashes with a leading-zero-bits rule. Nodes compare chainwork, not block count, to choose between branches, so many cheap blocks cannot beat fewer expensive ones.
