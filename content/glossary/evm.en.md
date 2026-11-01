+++
title = "EVM"
summary = "The Ethereum Virtual Machine: a stack machine with 256-bit words that runs contract bytecode and charges gas for every step."
category = "Blockchain"
related = ["bytecode", "opcode", "gas", "smart-contract"]
posts = ["bc-evm-internals-rust"]
+++

Each contract call gets a fresh [stack](/glossary/stack/) and memory, reads its input from calldata and can read and write the contract's persistent storage. Every node runs the same code on the same input and must reach the same result.
