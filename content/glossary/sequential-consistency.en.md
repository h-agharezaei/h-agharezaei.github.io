+++
title = "Sequential consistency"
summary = "All clients see one order of operations that keeps each client's own order, but it need not match real time."
category = "Distributed"
related = ["linearizability","causal-consistency"]
posts = ["ds-consistency-models"]
+++

Weaker than linearizability: a read may return an older value than a write that already finished on another client, as long as one legal global order exists.
