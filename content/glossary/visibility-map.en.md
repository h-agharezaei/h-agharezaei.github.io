+++
title = "Visibility map"
summary = "A per-table bitmap that marks heap pages where all rows are visible to every transaction."
category = "Databases"
related = ["vacuum", "index-only-scan"]
posts = ["db-composite-partial-covering-indexes", "db-mvcc-vacuum"]
+++

[VACUUM](/glossary/vacuum/) sets the bits; an update to a page clears its bit. Index Only Scans depend on it.
