+++
title = "Schnorr protocol"
summary = "A three-move proof of knowledge of a discrete log: commit R = r·G, get challenge c, answer s = r + c·x; also the basis of Schnorr signatures."
category = "Blockchain"
related = ["zero-knowledge-proof", "fiat-shamir", "discrete-logarithm", "nonce"]
posts = ["bc-zero-knowledge-rust"]
+++

The verifier checks s·G == R + c·X. With [Fiat-Shamir](/glossary/fiat-shamir/) it becomes a signature; Bitcoin's BIP-340 signatures are Schnorr over secp256k1. Reusing r for two challenges reveals x.
