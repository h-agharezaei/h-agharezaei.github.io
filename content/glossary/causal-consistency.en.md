+++
title = "Causal consistency"
summary = "If one operation could have influenced another, everyone sees them in that order; unrelated ones may differ."
category = "Distributed"
related = ["sequential-consistency","eventual-consistency"]
posts = ["ds-consistency-models"]
+++

A reply is seen after the question it answers, on every node. Concurrent, unrelated writes may appear in different orders on different nodes.
