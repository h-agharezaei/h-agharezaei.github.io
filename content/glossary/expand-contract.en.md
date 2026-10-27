+++
title = "Expand/contract"
summary = "A migration recipe in small safe steps: add the new shape, copy data, switch the app, drop the old shape."
category = "Databases"
related = ["backfill", "migration"]
posts = ["db-zero-downtime-migrations", "eng-refactoring-safely"]
+++

Every step is compatible with the code that is running at that moment, so no step needs downtime and each one can be rolled back until the last (the drop).
