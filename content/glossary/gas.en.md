+++
title = "Gas"
summary = "The unit the EVM uses to meter work: every opcode costs gas, and a call that runs out of gas halts and its state changes are undone."
category = "Blockchain"
related = ["evm", "opcode", "halting-problem"]
posts = ["bc-evm-internals-rust"]
+++

The sender sets a gas limit and pays for the gas used. Because every step costs something, a program with a loop always stops, either by finishing or by running out of gas.
