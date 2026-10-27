+++
title = "Anti-entropy"
summary = "A background process that compares replicas and copies the differences, whether or not anyone reads the data."
category = "Distributed"
related = ["merkle-tree", "read-repair"]
posts = ["ds-replication-quorum"]
+++

Usually built on a [Merkle tree](/glossary/merkle-tree/) so that comparing two large replicas costs little when they are almost equal.
