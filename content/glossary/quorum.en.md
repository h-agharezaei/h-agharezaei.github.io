+++
title = "Quorum"
summary = "A group of replicas whose agreement is required, usually a strict majority, so that any two quorums overlap."
category = "Distributed"
related = ["network-partition","split-brain"]
posts = ["ds-cap-pacelc", "ds-consensus-raft", "ds-replication-quorum"]
+++

With 3 replicas a quorum is 2. The overlap is why a minority side of a partition cannot make progress alone. See [network partition](/glossary/network-partition/).
