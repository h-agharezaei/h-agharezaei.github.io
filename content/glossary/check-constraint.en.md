+++
title = "CHECK constraint"
summary = "A rule on a table, such as balance_cents >= 0, that every written row must satisfy."
category = "Databases"
related = ["foreign-key", "acid"]
posts = ["db-transactions-acid"]
+++

A statement that would violate it fails with an error, and inside a transaction that failure aborts the whole transaction.
