+++
title = "SKIP LOCKED"
summary = "A `SELECT ... FOR UPDATE` option that skips rows other sessions have locked instead of waiting, used to build job queues."
category = "Databases"
related = ["lock"]
posts = ["db-locks-deadlocks"]
+++

With `FOR UPDATE SKIP LOCKED` each worker claims rows nobody else has locked, so several workers can take different jobs from the same table at once. It is meant for queue-like tables, not for general reads, because the result depends on who holds what at that moment.
