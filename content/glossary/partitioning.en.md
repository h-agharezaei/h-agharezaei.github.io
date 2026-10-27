+++
title = "Table partitioning"
summary = "Splitting one big logical table into smaller physical tables (partitions) by a key such as a date range, a list of values or a hash."
category = "Databases"
related = ["partition-pruning","default-partition","primary-key"]
posts = ["db-partitioning", "ds-sharding-consistent-hashing"]
+++

Splitting one big logical table into smaller physical tables (partitions) by a key such as a date range, a list of values or a hash. In PostgreSQL the parent table holds no rows itself; each row lives in exactly one partition. Queries and inserts still use the parent's name. See [partition pruning](/glossary/partition-pruning/).
