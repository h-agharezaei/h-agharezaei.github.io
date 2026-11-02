+++
title = "delegatecall"
summary = "An EVM call that runs another contract's code against the caller's storage, keeping msg.sender and msg.value."
category = "Blockchain"
related = ["proxy-pattern", "evm", "storage-collision"]
posts = ["bc-gas-optimization-proxies"]
+++

It is what makes [proxies](/glossary/proxy-pattern/) and libraries with state possible. Because the code writes to the caller's slots, both sides must agree on the storage layout.
