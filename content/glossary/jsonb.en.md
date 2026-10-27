+++
title = "JSONB"
summary = "A PostgreSQL column type that stores JSON in a parsed binary form that can be indexed and queried."
category = "Databases"
related = ["gin-index", "database-index"]
posts = ["db-jsonb-fulltext-search"]
+++

Unlike plain `json`, `jsonb` drops key order and duplicate keys, but supports operators such as `@>` (contains) and `?` (key exists) and GIN indexes. A JSONB value has no schema or type checks unless you add constraints. See [GIN index](/glossary/gin-index/).
