+++
title = "Peer discovery"
summary = "How a node finds addresses of other nodes to connect to in a P2P network."
category = "Blockchain"
related = ["peer-to-peer", "gossip-protocol"]
posts = ["bc-p2p-gossip"]
+++

Bitcoin nodes bootstrap from DNS seeds and then learn addresses from peers; Ethereum clients use a Kademlia-style discovery protocol over UDP. If an attacker controls all of a node's peers (an eclipse attack), the node sees only the attacker's view.
