+++
title = "Composite index"
summary = "An index on several columns, sorted by the first, then the second, and so on."
category = "Databases"
related = ["covering-index", "partial-index"]
posts = ["db-composite-partial-covering-indexes"]
+++

Order matters: `(a, b)` serves filters on `a` or on `a` and `b`, not efficiently on `b` alone. Put equality columns first and the range column last.
