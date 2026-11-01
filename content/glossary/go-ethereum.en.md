+++
title = "go-ethereum (geth)"
summary = "The Go implementation of an Ethereum execution client; its packages (ethclient, types, crypto, abi) are also used as a Go library."
category = "Blockchain"
related = ["json-rpc", "evm", "abigen"]
posts = ["bc-go-ethereum-client", "bc-event-indexer-go"]
+++

`ethclient` wraps the node's [JSON-RPC](/glossary/json-rpc/) API in typed Go methods such as `ChainID`, `BalanceAt` and `SendTransaction`. The same module ships [abigen](/glossary/abigen/), which generates Go code from a contract ABI.
