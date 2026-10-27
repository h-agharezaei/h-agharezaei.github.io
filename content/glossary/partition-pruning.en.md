+++
title = "Partition pruning"
summary = "The planner skipping partitions that cannot contain matching rows because the query filters on the partition key."
category = "Databases"
related = ["partitioning","query-planner"]
posts = ["db-partitioning"]
+++

The planner skipping partitions that cannot contain matching rows because the query filters on the partition key. Without a condition on the partition key every partition must be scanned. Pruning is controlled by the setting `enable_partition_pruning`. See [partitioning](/glossary/partitioning/).
