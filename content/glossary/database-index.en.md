+++
title = "Database index"
summary = "A separate sorted structure that lets the database find rows without reading the whole table."
category = "Databases"
related = ["b-tree", "query-plan"]
posts = ["db-indexes-btree-explain"]
+++

An index stores the values of one or more columns together with pointers to the table rows. Reads that match it get faster, but every insert, update and delete must also maintain it. The most common kind is the [B-tree](/glossary/b-tree/).
