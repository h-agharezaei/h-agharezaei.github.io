+++
title = "Write skew"
summary = "Two transactions read overlapping data, each updates a different row, and together they break a rule neither broke alone."
category = "Databases"
related = ["snapshot-isolation", "lost-update", "isolation-level"]
posts = ["db-isolation-levels-anomalies"]
+++

Classic example: two on-call doctors each check that the other is still on duty, then both go off duty. Snapshot isolation allows it; SERIALIZABLE does not.
