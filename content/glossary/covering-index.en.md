+++
title = "Covering index"
summary = "An index that contains every column a query needs, so the table is not read."
category = "Databases"
related = ["index-only-scan", "composite-index"]
posts = ["db-composite-partial-covering-indexes"]
+++

In PostgreSQL you add payload columns with `INCLUDE`; they are stored in the index but not used for sorting. It enables an [Index Only Scan](/glossary/index-only-scan/).
