+++
title = "Partial index"
summary = "An index that covers only the rows matching a WHERE condition."
category = "Databases"
related = ["primary-key"]
posts = ["db-schema-design-normalization", "db-composite-partial-covering-indexes"]
+++

A partial index is built with a WHERE clause and contains only matching rows. Combined with UNIQUE it enforces rules such as "at most one open order per customer" while allowing many rows with other statuses.
