+++
title = "Scatter-gather"
summary = "Sending a query to every shard and merging the partial answers, needed when the query does not contain the shard key."
category = "Distributed"
related = ["sharding", "hot-key"]
posts = ["ds-sharding-consistent-hashing"]
+++

The cost grows with the number of shards: every query makes one request per shard, and the slowest shard decides the latency. Queries that include the shard key go to one shard instead.
