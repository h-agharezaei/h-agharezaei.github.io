+++
title = "sol! macro"
summary = "An alloy macro that reads Solidity declarations at compile time and generates Rust types for calls, events and custom errors."
category = "Blockchain"
related = ["alloy", "contract-abi", "abigen", "function-selector"]
posts = ["bc-rust-alloy-client"]
+++

You paste the contract's interface (or point it at an [ABI](/glossary/contract-abi/) JSON file) and the macro expands it into structs with the right [selectors](/glossary/function-selector/) and encoding, plus one enum per contract for its errors. Unlike [abigen](/glossary/abigen/), no generated file is checked in: a change to the interface is a compile error at the call site.
