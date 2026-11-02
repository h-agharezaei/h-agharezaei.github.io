+++
title = "tx.origin"
summary = "The account that signed the transaction, unlike msg.sender, the immediate caller; unsafe for authorization."
category = "Blockchain"
related = ["access-control", "smart-contract"]
posts = ["bc-contract-security"]
+++

If a wallet checks `tx.origin == owner`, any contract the owner is tricked into calling can call the wallet and pass the check. Use `msg.sender`.
