+++
title = "Consensus"
summary = "Getting a group of nodes to agree on one value (or one ordered log) even when some nodes crash or messages are lost."
category = "Distributed"
related = ["quorum", "raft"]
posts = ["ds-consensus-raft"]
+++

Raft and Paxos are consensus algorithms. They need a majority of nodes alive, which is why a cluster of 2f+1 nodes tolerates f failures.
