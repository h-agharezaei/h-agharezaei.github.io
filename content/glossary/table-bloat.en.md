+++
title = "Table bloat"
summary = "Wasted space in a table or index left by dead row versions that were never reused."
category = "Databases"
related = ["dead-tuple", "vacuum"]
posts = ["db-mvcc-vacuum"]
+++

Plain `VACUUM` makes the space reusable inside the file but usually does not shrink it; `VACUUM FULL` rewrites the table and does.
