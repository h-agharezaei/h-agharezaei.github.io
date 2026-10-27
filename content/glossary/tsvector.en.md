+++
title = "tsvector"
summary = "A PostgreSQL type holding a document as a sorted list of normalized words (lexemes) with their positions, used for full-text search."
category = "Databases"
related = ["stemming", "gin-index"]
posts = ["db-jsonb-fulltext-search"]
+++

`to_tsvector('english', 'running shoes')` gives `'run':1 'shoe':2`. You match it against a `tsquery` with the `@@` operator, and index it with a [GIN index](/glossary/gin-index/).
