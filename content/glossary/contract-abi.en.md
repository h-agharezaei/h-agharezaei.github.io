+++
title = "Contract ABI"
summary = "The JSON description of a contract's functions, events and errors, and the rules for encoding calls and decoding results."
category = "Blockchain"
related = ["function-selector", "event-log", "abigen"]
posts = ["bc-go-ethereum-client", "bc-rust-alloy-client"]
+++

Calldata is a 4-byte [function selector](/glossary/function-selector/) followed by 32-byte encoded arguments. The compiler writes the ABI; clients such as [abigen](/glossary/abigen/) bindings use it to talk to the contract.
