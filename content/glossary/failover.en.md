+++
title = "Failover"
summary = "Switching to a standby as the new primary when the old one fails."
category = "Databases"
related = ["replication","split-brain"]
posts = ["db-replication-streaming"]
+++

Core PostgreSQL only gives you the promote command; detecting the failure, choosing a standby and fencing the old primary is done by external tools such as Patroni or repmgr.
