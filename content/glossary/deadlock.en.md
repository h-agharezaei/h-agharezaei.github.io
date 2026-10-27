+++
title = "Deadlock"
summary = "Two or more sessions each wait for a lock the other holds, so none can continue; the database aborts one of them."
category = "Databases"
related = ["lock", "transaction"]
posts = ["db-locks-deadlocks"]
+++

Session A holds row 1 and wants row 2, session B holds row 2 and wants row 1. PostgreSQL notices the cycle after `deadlock_timeout` and cancels one transaction with SQLSTATE `40P01`. The usual cure is to take [locks](/glossary/lock/) in the same order everywhere.
