+++
title = "Merkle tree"
summary = "A tree of hashes where each parent hashes its children, so equal root hashes mean equal data."
category = "Distributed"
related = ["anti-entropy"]
posts = ["ds-replication-quorum"]
+++

To find differences, compare roots and descend only into subtrees whose hashes differ. With few differences you compare a handful of nodes instead of every key.
