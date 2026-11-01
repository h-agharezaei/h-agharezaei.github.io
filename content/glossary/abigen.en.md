+++
title = "abigen"
summary = "A go-ethereum tool that generates typed Go bindings (pack, unpack, events, errors) from a contract ABI."
category = "Blockchain"
related = ["contract-abi", "go-ethereum"]
posts = ["bc-go-ethereum-client"]
+++

With `--v2` the generated code only packs and unpacks; calls and transactions go through the `bind/v2` package. Regenerate the bindings whenever the contract's ABI changes.
