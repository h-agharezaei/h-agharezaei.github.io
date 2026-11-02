+++
title = "Searcher"
summary = "A program that watches pending transactions and chain state, simulates them and submits transactions that capture MEV."
category = "Blockchain"
related = ["mev", "front-running", "arbitrage"]
posts = ["bc-mev-ordering"]
+++

A searcher decodes calldata, computes the result of different orderings off-chain and only sends transactions whose simulated profit beats their cost. Its targets range from [arbitrage](/glossary/arbitrage/) to sandwiches.
