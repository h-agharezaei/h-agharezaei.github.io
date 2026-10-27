+++
title = "Read repair"
summary = "When a read finds a replica holding an older version, the reader writes the newest version back to it."
category = "Distributed"
related = ["anti-entropy", "quorum"]
posts = ["ds-replication-quorum"]
+++

A cheap way to heal replicas using traffic you already have. Keys that are never read stay stale, so it needs [anti-entropy](/glossary/anti-entropy/) next to it.
