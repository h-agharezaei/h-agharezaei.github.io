+++
title = "Byzantine fault"
summary = "A failure where a node does not just crash but behaves arbitrarily: it lies, sends different answers to different peers, or acts maliciously."
category = "Blockchain"
related = ["consensus", "distributed-ledger"]
posts = ["bc-blockchain-for-programmers"]
+++

Crash-fault protocols such as Raft assume nodes are honest but may stop. Byzantine fault tolerant (BFT) protocols keep working while some participants are dishonest, which is the setting public blockchains are designed for. It costs more messages and, in classic BFT, more than two thirds honest nodes.
