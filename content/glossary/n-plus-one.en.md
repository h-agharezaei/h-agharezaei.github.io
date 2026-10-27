+++
title = "N+1 queries"
summary = "One query to fetch a list, then one more query per item in the list."
category = "Databases"
related = ["correlated-subquery", "sql-join"]
posts = ["db-slow-query-case-study", "py-sqlalchemy-postgres"]
+++

The application loads 100 orders with one query, then runs 100 more queries to load each customer. Every single query is fast, so no plan looks wrong; the cost is the round trips. The fix is one query with a join or `WHERE id = ANY(...)`.
