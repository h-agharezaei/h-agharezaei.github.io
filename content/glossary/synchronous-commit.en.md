+++
title = "synchronous_commit"
summary = "The PostgreSQL setting that decides whether COMMIT waits until its WAL is flushed to disk."
category = "Databases"
related = ["wal", "acid"]
posts = ["db-transactions-acid", "db-replication-streaming", "ds-cap-pacelc"]
+++

With the default `on`, a commit returns only after its WAL is flushed, which is what makes it durable. Turning it `off` is faster but a crash can lose the last few commits (the database stays consistent).
