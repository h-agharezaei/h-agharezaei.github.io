+++
title = "Checks-effects-interactions"
summary = "Order a function as: validate inputs, write state, and only then call other contracts or send ETH."
category = "Blockchain"
related = ["reentrancy", "smart-contract"]
posts = ["bc-contract-security"]
+++

If the state is already final when control leaves the contract, a callback finds nothing to exploit. It is the main defence against [reentrancy](/glossary/reentrancy/); a `nonReentrant` lock is a second layer.
