+++
title = "Rendezvous hashing"
summary = "Each key goes to the node with the highest hash(node, key) score (also called HRW)."
category = "Algorithms"
related = ["consistent-hashing"]
posts = ["algo-bloom-filter-consistent-hashing"]
+++

For every key you score each node with a hash of the pair and pick the highest. Removing a node only moves its own keys. It needs no ring, but a lookup costs O(number of nodes). Compare [Consistent hashing](/glossary/consistent-hashing/).
