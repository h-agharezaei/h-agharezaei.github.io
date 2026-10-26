+++
title = "Autovacuum"
summary = "The PostgreSQL background worker that runs VACUUM and ANALYZE automatically when a table has enough changes."
category = "Databases"
related = ["vacuum", "dead-tuple"]
posts = ["db-mvcc-vacuum"]
+++

Its thresholds are settings such as `autovacuum_vacuum_threshold` and `autovacuum_vacuum_scale_factor`; check the docs before changing them.
