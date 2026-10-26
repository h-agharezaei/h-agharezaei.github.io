+++
title = "HOT update"
summary = "Heap-Only Tuple update: a new row version stored in the same page with no new index entries, possible when no indexed column changes."
category = "Databases"
related = ["mvcc", "vacuum"]
posts = ["db-mvcc-vacuum"]
+++

It needs free space in the same page. `n_tup_hot_upd` in `pg_stat_user_tables` counts them.
