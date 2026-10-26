+++
title = "Phantom read"
summary = "Running the same query twice in one transaction and getting a different set of rows."
category = "Databases"
related = ["isolation-level", "non-repeatable-read"]
posts = ["db-isolation-levels-anomalies"]
+++

A row that matches your WHERE clause was inserted (or removed) and committed by someone else in between. The rows you already read did not change, new ones appeared.
