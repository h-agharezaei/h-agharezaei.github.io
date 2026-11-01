+++
title = "Proxy pattern"
summary = "A small contract that holds the state and forwards every call to a replaceable implementation contract."
category = "Blockchain"
related = ["delegatecall", "eip-1967", "storage-collision"]
posts = ["bc-gas-optimization-proxies"]
+++

Users keep one address while the code behind it is upgraded. Forwarding uses [delegatecall](/glossary/delegatecall/). Variants include transparent and UUPS proxies, which differ in where the upgrade logic lives.
