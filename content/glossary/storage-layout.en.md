+++
title = "Storage layout"
summary = "Which 32-byte storage slot (and offset) each state variable of a contract occupies."
category = "Blockchain"
related = ["solidity", "evm", "keccak-256"]
posts = ["bc-solidity-first-contract"]
+++

Solidity assigns slots in declaration order and packs small values together. A mapping only reserves a slot number `p`; the value for key `k` lives at `keccak256(k . p)`. `forge inspect <Contract> storageLayout` prints it.
