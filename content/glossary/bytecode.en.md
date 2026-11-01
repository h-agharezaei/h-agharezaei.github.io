+++
title = "Bytecode"
summary = "A program encoded as a sequence of bytes for a virtual machine instead of a real CPU, such as the code stored in an Ethereum contract account."
category = "Blockchain"
related = ["opcode", "evm"]
posts = ["bc-evm-internals-rust"]
+++

Compilers like Solidity's produce it; nodes store and run it. Bytes after a `PUSH` are data, not instructions, which matters when checking jump targets.
