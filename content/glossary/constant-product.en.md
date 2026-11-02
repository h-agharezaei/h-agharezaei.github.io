+++
title = "Constant product"
summary = "The AMM rule x * y = k: a swap may not decrease the product of the two reserves."
category = "Blockchain"
related = ["amm", "liquidity-pool"]
posts = ["bc-amm-constant-product"]
+++

Putting dx of one token in gives dy = y * dx / (x + dx) of the other, before fees. The price y / x moves with every trade, and larger trades get a worse average price. Fees make k grow slightly on each swap.
