+++
title = "Difficulty target"
summary = "The threshold a block hash must be below; a lower target means more hash attempts per block."
category = "Blockchain"
related = ["proof-of-work", "difficulty-adjustment", "chainwork"]
posts = ["bc-proof-of-work-mining"]
+++

Bitcoin stores a full 256-bit target in a compact form in each header. A toy chain can instead require a number of leading zero bits: each extra bit halves the target and doubles the expected work.
