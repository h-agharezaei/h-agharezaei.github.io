+++
title = "Opcode"
summary = "One instruction of a virtual machine, encoded as a byte; for example in the EVM 0x01 is ADD and 0x55 is SSTORE."
category = "Blockchain"
related = ["bytecode", "evm"]
posts = ["bc-evm-internals-rust"]
+++

Some opcodes carry immediate data after them: `PUSH1` (0x60) is followed by one byte that gets pushed. An interpreter reads an opcode, does its work and moves to the next one.
