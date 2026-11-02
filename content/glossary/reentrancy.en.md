+++
title = "Reentrancy"
summary = "An external call lets the callee call back into the caller before the caller has finished updating its state."
category = "Blockchain"
related = ["checks-effects-interactions", "smart-contract", "erc-721"]
posts = ["bc-contract-security"]
+++

Classic case: a vault sends ETH before zeroing the balance, and the recipient's `receive()` calls `withdraw()` again. Variants: cross-function (reenter through another function) and read-only (another contract reads a half-updated `view`). Fix with [checks-effects-interactions](/glossary/checks-effects-interactions/) plus a lock.
