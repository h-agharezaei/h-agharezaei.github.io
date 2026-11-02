+++
title = "secp256k1"
summary = "The elliptic curve y² = x³ + 7 over a 256-bit prime field, used for keys and signatures in Bitcoin and Ethereum."
category = "Blockchain"
related = ["ecdsa", "keccak-256"]
posts = ["bc-keys-ecdsa-addresses", "bc-bitcoin-script-rust"]
+++

A private key is a 256-bit number d and the public key is the point d·G. Go's standard `crypto/ecdsa` does not ship this curve, so Go code uses a library such as `github.com/decred/dcrd/dcrec/secp256k1/v4`.
