+++
title = "Oracle"
summary = "Whatever puts outside data, usually a price, on-chain for contracts to read; contracts cannot fetch it themselves."
category = "Blockchain"
related = ["twap", "price-manipulation", "health-factor"]
posts = ["bc-lending-liquidation", "bc-oracles"]
+++

Lending markets trust their oracle more than any other input: it decides borrow limits and liquidations. Common designs are a time-weighted average from an on-chain pool ([TWAP](/glossary/twap/)) and push feeds where reporters publish prices; both need freshness checks.
