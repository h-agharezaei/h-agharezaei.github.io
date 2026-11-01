+++
title = "ECDSA"
summary = "Elliptic Curve Digital Signature Algorithm: signs a hash with a private key on an elliptic curve; a signature is the pair (r, s)."
category = "Blockchain"
related = ["secp256k1", "rfc-6979", "signature-malleability", "digital-signature", "nonce"]
posts = ["bc-keys-ecdsa-addresses", "bc-bitcoin-script-rust"]
+++

Bitcoin and Ethereum sign transactions with ECDSA on [secp256k1](/glossary/secp256k1/). Each signature needs a secret per-signature [nonce](/glossary/nonce/) k; reusing k with the same key reveals the private key.
