+++
title = "Backfill"
summary = "Filling a new column for existing rows, in small batches so locks and transactions stay short."
category = "Databases"
related = ["expand-contract", "migration"]
posts = ["db-zero-downtime-migrations"]
+++

One giant `UPDATE` holds row locks and produces dead rows all at once. A loop that updates an id range per batch keeps each transaction small.
