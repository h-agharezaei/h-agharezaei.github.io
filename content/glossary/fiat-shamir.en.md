+++
title = "Fiat-Shamir transform"
summary = "Makes an interactive proof non-interactive by deriving the verifier's challenge from a hash of the transcript."
category = "Blockchain"
related = ["schnorr", "zero-knowledge-proof"]
posts = ["bc-zero-knowledge-rust"]
+++

The hash must cover everything: domain tag, public key, commitment and message. Leaving the commitment out lets anyone forge a proof without the secret.
