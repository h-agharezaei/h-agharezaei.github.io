+++
title = "MVCC"
summary = "Multi-version concurrency control: the database keeps several versions of a row so readers and writers do not block each other."
category = "Databases"
related = ["vacuum", "dead-tuple"]
posts = ["db-mvcc-vacuum", "db-jsonb-fulltext-search", "db-locks-deadlocks"]
+++

In PostgreSQL an `UPDATE` does not overwrite a row: it writes a new version and marks the old one as ended. Each query uses a snapshot to decide which versions it may see. The price is dead versions that [VACUUM](/glossary/vacuum/) must clean up later.
