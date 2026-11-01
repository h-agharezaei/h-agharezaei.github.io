+++
title = "Borrow index"
summary = "A single growing number that turns every borrower's stored scaled debt into current debt, so interest accrues in O(1)."
category = "Blockchain"
related = ["liquidation", "health-factor"]
posts = ["bc-lending-liquidation"]
+++

A borrow stores amount / index; current debt is that times the latest index. Accruing interest only updates the index, never each borrower. Shares in a pool or vault use the same idea.
