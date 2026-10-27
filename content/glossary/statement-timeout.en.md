+++
title = "statement_timeout"
summary = "A PostgreSQL setting that cancels any single statement running longer than the given time."
category = "Databases"
related = ["lock-timeout","idle-in-transaction"]
posts = ["db-connection-pooling"]
+++

When a statement exceeds the limit the server cancels it with SQLSTATE `57014`; the connection stays usable. It can be set per session, role or database. Related: [lock timeout](/glossary/lock-timeout/).
