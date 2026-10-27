+++
title = "Planner statistics"
summary = "Per-column summaries that `ANALYZE` stores for the planner."
category = "Databases"
related = ["query-planner", "extended-statistics"]
posts = ["db-planner-statistics", "db-slow-query-case-study"]
+++

They include distinct counts, most common values, histograms and correlation, visible in `pg_stats`. Stale or missing statistics lead to bad row estimates and bad plans.
