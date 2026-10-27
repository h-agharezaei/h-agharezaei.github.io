+++
title = "PgBouncer"
summary = "A separate connection pooler placed between applications and PostgreSQL."
category = "Databases"
related = ["connection-pool","idle-in-transaction"]
posts = ["db-connection-pooling"]
+++

Many client connections share a few server connections. In session mode a client keeps one server connection for its whole session; in transaction mode it borrows one only for the length of a transaction, so session state does not carry over between transactions.
