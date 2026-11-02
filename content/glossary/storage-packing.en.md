+++
title = "Storage packing"
summary = "Declaring small state variables next to each other so Solidity stores them in one 32-byte slot."
category = "Blockchain"
related = ["storage-layout", "gas", "evm"]
posts = ["bc-gas-optimization-proxies"]
+++

Fewer slots means fewer expensive storage reads and writes when the values are used together, e.g. two `uint112` reserves and a `uint32` timestamp. Narrowing types requires checked casts, because a cast truncates silently.
