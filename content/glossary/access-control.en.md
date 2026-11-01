+++
title = "Access control"
summary = "Rules about who may call which function; in contracts usually an explicit msg.sender check such as onlyOwner."
category = "Blockchain"
related = ["authorization", "least-privilege", "tx-origin"]
posts = ["bc-contract-security"]
+++

Common bugs are a missing check on a privileged function and an `initialize()` that anyone can call, or call again. Every privileged function deserves a test that a stranger is rejected.
