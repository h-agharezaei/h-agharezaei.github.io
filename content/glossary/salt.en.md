+++
title = "Salt"
summary = "A random value stored next to a password hash so equal passwords give different hashes."
category = "Security"
related = ["password-hashing", "pepper"]
posts = ["sec-password-hashing", "sec-crypto-mistakes", "openssh-musl-password-bypass-cve-2026-123158"]
+++

The salt is not secret. It stops precomputed tables and makes the attacker work on each account separately.
