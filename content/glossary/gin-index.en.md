+++
title = "GIN index"
summary = "An inverted index in PostgreSQL that maps each element inside a value (a JSON key, a word) to the rows that contain it."
category = "Databases"
related = ["database-index", "b-tree", "jsonb", "tsvector"]
posts = ["db-jsonb-fulltext-search"]
+++

GIN (Generalized Inverted Index) suits values that contain many parts, such as JSONB documents, arrays and text search vectors. A lookup finds the rows for each part and combines them; writes are more expensive than with a [B-tree](/glossary/b-tree/).
