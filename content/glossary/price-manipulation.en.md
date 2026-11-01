+++
title = "Price manipulation"
summary = "Moving the price a contract reads, often a pool's spot price inside one transaction, to borrow or withdraw more than the assets are worth."
category = "Blockchain"
related = ["oracle", "twap", "flash-loan"]
posts = ["bc-oracles"]
+++

No line of code needs a bug: the protocol simply trusts a number the attacker can move for the price of swap fees. Defences are manipulation-resistant [oracles](/glossary/oracle/), freshness and deviation checks.
