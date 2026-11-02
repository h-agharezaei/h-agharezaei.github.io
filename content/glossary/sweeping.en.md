+++
title = "Sweeping"
summary = "Moving funds from many deposit addresses into a few exchange-controlled wallets, such as the hot wallet or cold storage."
category = "Blockchain"
related = ["deposit-address", "hot-wallet", "cold-wallet"]
posts = ["bc-exchange-deposits-withdrawals"]
+++

Each sweep is an ordinary on-chain transaction signed with the deposit address's key. For an ERC-20 token on Ethereum the deposit address also needs ETH for gas, so sweeping has a cost and is usually batched or done above a threshold.
