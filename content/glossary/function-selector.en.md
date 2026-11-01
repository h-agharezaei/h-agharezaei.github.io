+++
title = "Function selector"
summary = "The first 4 bytes of keccak256 of a function signature; calldata starts with it so the contract knows which function to run."
category = "Blockchain"
related = ["keccak-256", "evm", "solidity"]
posts = ["bc-solidity-first-contract", "bc-go-ethereum-client", "bc-rust-alloy-client"]
+++

For `transfer(address,uint256)` the selector is `0xa9059cbb`. The compiler emits a dispatcher that compares the first 4 bytes of calldata with each selector. `cast sig` computes one.
