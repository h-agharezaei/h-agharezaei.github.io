+++
title = "Leader election"
summary = "Choosing one node to coordinate for a period; in Raft a candidate needs votes from a majority in a new term."
category = "Distributed"
related = ["raft", "quorum"]
posts = ["ds-consensus-raft"]
+++

Followers that stop hearing heartbeats time out at random moments, so usually one candidate starts first and wins.
