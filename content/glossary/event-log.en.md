+++
title = "Event log"
summary = "Data a contract emits into the transaction receipt: up to 4 indexed topics plus data, readable off-chain but not by contracts."
category = "Blockchain"
related = ["solidity", "erc-20", "keccak-256"]
posts = ["bc-solidity-first-contract", "bc-erc20-erc721"]
+++

The first topic is usually `keccak256` of the event signature; `indexed` parameters become the other topics. Wallets and indexers find transfers by filtering logs, which is why [ERC-20](/glossary/erc-20/) requires a `Transfer` event.
