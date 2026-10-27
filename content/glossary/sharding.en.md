+++
title = "Sharding"
summary = "Splitting one dataset across several nodes by a shard key, so each node owns only part of the data."
category = "Distributed"
related = ["consistent-hashing", "partitioning", "hot-key"]
posts = ["ds-sharding-consistent-hashing"]
+++

Each row (or key) belongs to exactly one shard, chosen by range, hash or a lookup directory. It adds write capacity and room for data, but queries and transactions that span shards become expensive. It differs from [partitioning](/glossary/partitioning/) inside one database node.
