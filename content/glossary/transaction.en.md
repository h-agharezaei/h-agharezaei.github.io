+++
title = "Transaction"
summary = "A group of statements that the database treats as one unit: all of them take effect, or none do."
category = "Databases"
related = ["acid", "savepoint"]
posts = ["db-transactions-acid", "db-mvcc-vacuum", "node-postgres-pg"]
+++

In PostgreSQL every statement runs inside a transaction; without `BEGIN` each statement gets its own (autocommit). `COMMIT` makes the changes permanent and `ROLLBACK` discards them.
