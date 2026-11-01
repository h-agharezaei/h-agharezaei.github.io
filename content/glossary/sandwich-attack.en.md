+++
title = "Sandwich attack"
summary = "Placing a trade just before and another just after a victim's swap to profit from the price move it causes."
category = "Blockchain"
related = ["slippage", "amm"]
posts = ["bc-amm-constant-product", "bc-mev-ordering"]
+++

The attacker buys first, the victim buys at a worse price, the attacker sells. It works because pending transactions are public and ordering can be influenced. A tight minimum output limits the damage.
