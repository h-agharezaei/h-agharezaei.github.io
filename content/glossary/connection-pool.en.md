+++
title = "Connection pool"
summary = "A set of open database connections that are lent out and reused."
category = "Databases"
related = ["transaction"]
posts = ["node-postgres-pg", "db-connection-pooling"]
+++

Opening a database connection is slow and the server limits how many exist. A pool opens a few, lends one for each query or transaction, and takes it back on release. When all are busy, callers wait.
