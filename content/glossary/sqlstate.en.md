+++
title = "SQLSTATE"
summary = "A five-character standard error code, e.g. 23505 for a unique violation."
category = "Databases"
related = ["foreign-key", "primary-key"]
posts = ["db-relational-sql-essentials", "db-isolation-levels-anomalies"]
+++

Applications should branch on SQLSTATE, not on the error text. Class 23 covers integrity violations: 23505 unique, 23503 foreign key, 23514 check.
