+++
title = "Advisory lock"
summary = "An application-defined lock on a number; the database enforces it but attaches no meaning to it."
category = "Databases"
related = ["lock"]
posts = ["db-locks-deadlocks"]
+++

`pg_advisory_lock(42)` and `pg_try_advisory_lock(42)` lock a key you choose, not a row or table. Everyone who uses the same key must cooperate. It is handy for "only one instance runs this job".
