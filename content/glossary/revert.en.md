+++
title = "Revert"
summary = "Stopping an EVM call and undoing all its state changes, optionally returning error data."
category = "Blockchain"
related = ["gas", "evm", "solidity"]
posts = ["bc-solidity-first-contract"]
+++

In Solidity, `revert CustomError(args)` or a failed `require` reverts. A reverted transaction is still included in a block and the sender still pays for the [gas](/glossary/gas/) used; only the state changes are dropped.
