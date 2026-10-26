+++
title = "Savepoint"
summary = "A named point inside a transaction that you can roll back to without abandoning the whole transaction."
category = "Databases"
related = ["transaction"]
posts = ["db-transactions-acid"]
+++

`SAVEPOINT s1` marks the point and `ROLLBACK TO s1` undoes everything after it; the transaction stays open and usable.
