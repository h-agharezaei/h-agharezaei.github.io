+++
title = "Hot key"
summary = "A single key that receives so much traffic that the shard owning it is overloaded no matter how evenly the other keys are spread."
category = "Distributed"
related = ["sharding", "scatter-gather"]
posts = ["ds-sharding-consistent-hashing"]
+++

Changing the hash function does not help, because the same key always lands on the same shard. A common mitigation is splitting the key with a suffix (salt), which spreads writes but makes reads touch every suffix.
