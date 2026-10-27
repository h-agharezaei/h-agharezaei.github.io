+++
title = "Query planner"
summary = "The part of the database that chooses how to run a query."
category = "Databases"
related = ["planner-statistics", "selectivity"]
posts = ["db-planner-statistics", "db-partitioning"]
+++

It estimates the cost of candidate plans from statistics and picks the cheapest. `EXPLAIN` shows the chosen plan.
