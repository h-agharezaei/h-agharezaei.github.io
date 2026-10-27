+++
title = "lock_timeout"
summary = "A setting that makes a statement give up with an error if it waits too long for a lock."
category = "Databases"
related = ["lock", "migration"]
posts = ["db-zero-downtime-migrations"]
+++

Put it on every DDL statement in production and retry, so a waiting `ALTER TABLE` does not queue up all other queries behind it.
