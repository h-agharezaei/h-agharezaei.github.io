+++
title = "Query plan"
summary = "The tree of steps the database chooses to run a query, shown by EXPLAIN."
category = "Databases"
related = ["database-index"]
posts = ["db-indexes-btree-explain", "py-data-csv-sqlite"]
+++

The planner estimates a cost for each possible way to run the query (scan the table, use an index, which join order) and picks the cheapest. `EXPLAIN` shows the plan; `EXPLAIN ANALYZE` also runs the query and adds the real row counts.
