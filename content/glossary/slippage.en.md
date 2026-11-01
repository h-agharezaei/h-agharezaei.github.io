+++
title = "Slippage"
summary = "The gap between the quoted result of a trade and what it actually gets when it executes."
category = "Blockchain"
related = ["amm", "sandwich-attack"]
posts = ["bc-amm-constant-product"]
+++

Other transactions can move the price between quoting and execution. A swap protects itself with a minimum output (slippage tolerance) and a deadline; a swap without them accepts any price.
