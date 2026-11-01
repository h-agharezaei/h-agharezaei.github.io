+++
title = "Storage collision"
summary = "Two pieces of code that use the same storage slot for different variables, so each reads the other's data."
category = "Blockchain"
related = ["proxy-pattern", "delegatecall", "storage-layout"]
posts = ["bc-gas-optimization-proxies"]
+++

Typical cause: a new implementation version reorders, removes or retypes state variables. Only append new variables, and compare storage layouts before an upgrade.
