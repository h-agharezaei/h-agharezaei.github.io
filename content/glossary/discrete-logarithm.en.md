+++
title = "Discrete logarithm"
summary = "Given a group element X = x·G, finding x; believed infeasible on curves like secp256k1, which is what keeps private keys secret."
category = "Blockchain"
related = ["secp256k1", "schnorr"]
posts = ["bc-zero-knowledge-rust"]
+++

Computing x·G is cheap; going back is the discrete logarithm problem. ECDSA and Schnorr keys rely on it being hard.
