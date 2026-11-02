+++
title = "Zero-knowledge proof"
summary = "A protocol that convinces a verifier a statement is true without revealing anything else, such as the secret behind it."
category = "Blockchain"
related = ["schnorr", "fiat-shamir", "zk-snark", "zk-stark"]
posts = ["bc-zero-knowledge-rust"]
+++

It must be complete (an honest prover convinces), sound (a cheater fails except with negligible probability) and zero-knowledge (the verifier could simulate what it saw). A [Schnorr](/glossary/schnorr/) proof is the classic small example.
