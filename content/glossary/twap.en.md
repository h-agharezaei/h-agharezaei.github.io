+++
title = "TWAP"
summary = "Time-weighted average price: a price averaged over a window of seconds, computed from a cumulative price-times-time counter."
category = "Blockchain"
related = ["oracle", "price-manipulation", "amm"]
posts = ["bc-oracles"]
+++

The pool adds price × seconds to a counter before each change; two readings divided by the time between them give the average. A price pushed inside one transaction has zero weight. The cost is lag: a real move shows up slowly.
