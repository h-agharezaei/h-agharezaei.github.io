+++
title = "Keccak-256"
summary = "The original Keccak hash that Ethereum uses; its padding differs from the standardized SHA3-256, so the outputs differ."
category = "Blockchain"
related = ["eip-55", "secp256k1"]
posts = ["bc-keys-ecdsa-addresses"]
+++

Keccak-256 of empty input starts with `c5d24601`. In Go use `sha3.NewLegacyKeccak256` from `golang.org/x/crypto/sha3`, not `sha3.New256`.
