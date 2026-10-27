+++
title = "checksum database"
summary = "A public append-only log of module hashes (Go uses sum.golang.org) that detects a module changing between users."
category = "Security"
related = ["checksum", "lockfile", "software-supply-chain"]
posts = ["sec-supply-chain-vulns"]
+++

The first time you add a module, Go compares its hash with the database and records it in go.sum. Later downloads must match go.sum.
