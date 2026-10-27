+++
title = "Generated column"
summary = "A column whose value is computed from other columns of the same row by an expression, and stored automatically."
category = "Databases"
related = ["tsvector", "database-index"]
posts = ["db-jsonb-fulltext-search"]
+++

In PostgreSQL, `GENERATED ALWAYS AS (expr) STORED` recomputes the value on every insert and update, and you cannot write to it directly. A common use is a precomputed `tsvector` that you can index.
