+++
title = "alloy"
summary = "A Rust library for Ethereum: providers over JSON-RPC, local signers, transaction builders and the sol! macro for contract types."
category = "Blockchain"
related = ["json-rpc", "sol-macro", "go-ethereum", "contract-abi"]
posts = ["bc-rust-alloy-client"]
+++

alloy plays the role in Rust that [go-ethereum](/glossary/go-ethereum/)'s `ethclient` and `bind` packages play in Go. A `Provider` wraps the node's [JSON-RPC](/glossary/json-rpc/) API; with a wallet attached, "fillers" add nonce, gas limit, fees and chain ID before signing a transaction.
