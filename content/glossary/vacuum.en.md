+++
title = "VACUUM"
summary = "The PostgreSQL maintenance command that removes dead row versions and updates the visibility map."
category = "Databases"
related = ["visibility-map"]
posts = ["db-composite-partial-covering-indexes", "db-mvcc-vacuum"]
+++

Autovacuum runs it in the background; you can also run `VACUUM table` by hand. Frequent updates need it to keep up.
