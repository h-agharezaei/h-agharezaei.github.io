+++
title = "Split-brain"
summary = "Two nodes both believe they are the primary and accept different writes."
category = "Databases"
related = ["failover","replication"]
posts = ["db-replication-streaming"]
+++

After a promotion, an old primary that is still running keeps accepting writes and their histories diverge. Merging them afterwards is manual and often lossy.
