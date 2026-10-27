+++
title = "Trigram"
summary = "A group of three consecutive characters; comparing the trigram sets of two strings gives a similarity score used for fuzzy matching."
category = "Databases"
related = ["gin-index"]
posts = ["db-jsonb-fulltext-search"]
+++

The PostgreSQL extension `pg_trgm` provides `similarity()`, the `%` operator and trigram operator classes for [GIN indexes](/glossary/gin-index/), which also speed up `LIKE '%text%'`.
