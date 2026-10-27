+++
title = "Migration"
summary = "A versioned change to the database schema, applied in order by a script or a tool."
category = "Databases"
related = ["table-rewrite", "expand-contract"]
posts = ["db-zero-downtime-migrations"]
+++

Typical examples are adding a column or an index. The risk is not the SQL itself but the [locks](/glossary/lock/) it takes on a live table. Tools such as goose or Flyway only run the files in order; they do not make a dangerous statement safe.
