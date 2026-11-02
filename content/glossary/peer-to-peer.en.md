+++
title = "Peer-to-peer (P2P)"
summary = "A network where nodes connect to each other directly as equals, with no central server."
category = "Blockchain"
related = ["gossip-protocol", "peer-discovery", "sybil-attack"]
posts = ["bc-p2p-gossip"]
+++

Each node is both client and server: it accepts connections, dials others and serves the same data. Because no peer is trusted, every node validates what it receives before using or forwarding it.
