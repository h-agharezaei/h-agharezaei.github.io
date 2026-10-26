+++
title = "Selectivity"
summary = "The fraction of rows a condition keeps."
category = "Databases"
related = ["query-planner", "planner-statistics"]
posts = ["db-planner-statistics"]
+++

A condition matching 0.1% of rows is highly selective and favors an index; one matching 70% is not, and a sequential scan is usually cheaper.
