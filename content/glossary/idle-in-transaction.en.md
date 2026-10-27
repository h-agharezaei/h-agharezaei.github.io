+++
title = "Idle in transaction"
summary = "A session that opened a transaction and is doing nothing, still holding its connection and locks."
category = "Databases"
related = ["transaction","connection-pool","statement-timeout"]
posts = ["db-connection-pooling"]
+++

In `pg_stat_activity` this is `state = 'idle in transaction'`: BEGIN was sent, the application stopped sending statements. The connection cannot be reused, and locks and the snapshot stay held. `idle_in_transaction_session_timeout` ends such sessions. See [transaction](/glossary/transaction/).
