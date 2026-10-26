+++
title = "Index Only Scan"
summary = "A plan node that answers a query from the index alone, without visiting the table."
category = "Databases"
related = ["covering-index", "visibility-map"]
posts = ["db-composite-partial-covering-indexes"]
+++

It still checks the [visibility map](/glossary/visibility-map/); for pages not marked all-visible it fetches the table row (shown as `Heap Fetches`).
