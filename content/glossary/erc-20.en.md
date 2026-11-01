+++
title = "ERC-20"
summary = "The Ethereum standard interface for fungible tokens: balanceOf, transfer, approve, allowance, transferFrom and Transfer/Approval events."
category = "Blockchain"
related = ["erc-721", "event-log", "smart-contract"]
posts = ["bc-erc20-erc721"]
+++

An ERC-20 token is a contract with a mapping from address to balance. `decimals` only tells wallets how to display the integer amounts. Transfers are announced through `Transfer` [logs](/glossary/event-log/).
