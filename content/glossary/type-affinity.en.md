+++
title = "Type affinity"
summary = "SQLite's rule that a column prefers a type and converts values when it can, but does not strictly enforce it."
category = "Databases"
related = []
posts = ["py-data-csv-sqlite"]
+++

In SQLite a column declared `INTEGER` has integer affinity: the text `'12'` is stored as the integer 12, but `'abc'` is stored as text without an error. Each value carries its own type. `STRICT` tables enforce the declared type.
