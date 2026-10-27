+++
title = "Replicated log"
summary = "An ordered list of commands copied to several nodes; if every node applies the same log in order, their state machines end up identical."
category = "Distributed"
related = ["raft", "consensus"]
posts = ["ds-consensus-raft"]
+++

An entry is committed once a majority stores it (and, in Raft, the leader's own term rules are met). Only committed entries are applied.
