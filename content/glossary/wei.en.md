+++
title = "Wei"
summary = "The smallest unit of ether: 1 ether = 10^18 wei. Nodes and contracts only deal in wei, as integers."
category = "Blockchain"
related = ["gas", "eip-1559"]
posts = ["bc-go-ethereum-client", "bc-rust-alloy-client"]
+++

Gas prices are usually shown in gwei (10^9 wei). Amounts exceed 64 bits easily, so Go code keeps them in `*big.Int` and formats ether only for display.
