+++
title = "Hash slot"
summary = "One of a fixed number of logical buckets that keys hash into; whole slots, not single keys, are assigned to and moved between nodes."
category = "Distributed"
related = ["sharding", "consistent-hashing"]
posts = ["ds-sharding-consistent-hashing"]
+++

A key maps to slot = hash(key) mod S with S fixed, and a table maps slots to nodes. Adding a node moves some slots, so the key-to-slot mapping never changes. According to its docs Redis Cluster uses 16384 slots.
