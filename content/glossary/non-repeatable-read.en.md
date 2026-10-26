+++
title = "Non-repeatable read"
summary = "Reading the same row twice in one transaction and getting different values."
category = "Databases"
related = ["isolation-level", "phantom-read"]
posts = ["db-isolation-levels-anomalies"]
+++

It happens when another transaction commits a change between your two reads. PostgreSQL allows it at READ COMMITTED and prevents it at REPEATABLE READ.
