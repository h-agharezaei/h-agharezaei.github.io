+++
title = "Sargable"
summary = "A condition written so an index can be used for it."
category = "Databases"
related = ["selectivity"]
posts = ["db-planner-statistics", "db-composite-partial-covering-indexes"]
+++

`email = 'a'` is sargable; `lower(email) = 'a'` is not unless an index on `lower(email)` exists. Casting the column or a leading `%` also breaks it.
