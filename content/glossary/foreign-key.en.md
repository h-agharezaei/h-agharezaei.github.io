+++
title = "Foreign key"
summary = "A column that must match a primary key value in another table."
category = "Databases"
related = ["primary-key", "relational-model"]
posts = ["db-relational-sql-essentials", "db-schema-design-normalization"]
+++

A foreign key makes the database refuse rows that point at something that does not exist, and refuse deleting a row that is still referenced (SQLSTATE 23503).
