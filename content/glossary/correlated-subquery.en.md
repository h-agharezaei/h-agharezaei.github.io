+++
title = "Correlated subquery"
summary = "A subquery that refers to the outer row, so it runs once per outer row."
category = "Databases"
related = ["query-plan", "database-index"]
posts = ["db-slow-query-case-study"]
+++

`SELECT c.id, (SELECT count(*) FROM orders o WHERE o.customer_id = c.id) FROM customers c` runs the inner query for every customer. It is fine with an index and few rows, and very costly otherwise. A `JOIN` with `GROUP BY` often lets the planner do the work in one pass.
