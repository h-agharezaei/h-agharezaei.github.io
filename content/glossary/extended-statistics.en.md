+++
title = "Extended statistics"
summary = "Multi-column statistics created with `CREATE STATISTICS`."
category = "Databases"
related = ["planner-statistics"]
posts = ["db-planner-statistics"]
+++

By default the planner treats columns as independent. Extended statistics such as `dependencies` teach it that, for example, a country determines a region.
