+++
title = "Lost update"
summary = "Two transactions read the same value, both write a result computed from it, and one write silently overwrites the other."
category = "Databases"
related = ["isolation-level", "write-skew"]
posts = ["db-isolation-levels-anomalies"]
+++

Typical cause: read-modify-write in application code. Fixes: do the arithmetic in SQL (`SET balance = balance - 10`), lock the row with `SELECT ... FOR UPDATE`, or use a higher isolation level and retry.
