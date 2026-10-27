+++
title = "Raft"
summary = "A consensus algorithm built from leader election, log replication and safety rules, designed to be easier to understand than Paxos."
category = "Distributed"
related = ["consensus", "leader-election", "replicated-log"]
posts = ["ds-consensus-raft"]
+++

Raft was described by Ongaro and Ousterhout. Time is split into terms; each term has at most one leader, and only the leader appends to the log.
