+++
title = "Last write wins"
summary = "A conflict rule that keeps the value with the highest timestamp and discards the others."
category = "Distributed"
related = ["clock-skew"]
posts = ["ds-why-distributed-is-hard", "ds-cap-pacelc", "ds-logical-clocks", "ds-replication-quorum"]
+++

It is simple, but with skewed clocks the write that is really newer can carry a smaller timestamp and be lost silently.
