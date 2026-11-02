+++
title = "BIP-44"
summary = "A convention for BIP-32 paths: m / purpose' / coin_type' / account' / change / address_index."
category = "Blockchain"
related = ["bip-32", "hd-wallet"]
posts = ["bc-hd-wallets-rust"]
+++

Purpose is 44, coin_type comes from the SLIP-44 registry (60 for Ether, 0 for Bitcoin). The first three levels are hardened. For Ethereum the usual addresses are m/44'/60'/0'/0/i.
