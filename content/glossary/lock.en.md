+++
title = "Lock"
summary = "A mechanism that makes a session wait before touching data another session is using; PostgreSQL has table-level and row-level locks."
category = "Databases"
related = ["deadlock", "skip-locked", "advisory-lock"]
posts = ["db-locks-deadlocks"]
+++

Some operations must not run at the same time. A lock lets the second session wait (or fail fast) until the first one commits or rolls back. In PostgreSQL locks are held until the end of the [transaction](/glossary/transaction/), and a cycle of waits becomes a [deadlock](/glossary/deadlock/).
