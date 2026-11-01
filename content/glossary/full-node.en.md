+++
title = "Full node"
summary = "A node that downloads and validates every block and transaction itself instead of trusting others."
category = "Blockchain"
related = ["spv", "mempool", "initial-block-download"]
posts = ["bc-toy-node-go"]
+++

It keeps the current state (the UTXO set in Bitcoin) and relays valid data. A light ([SPV](/glossary/spv/)) client checks only headers and inclusion proofs.
