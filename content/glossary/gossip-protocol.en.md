+++
title = "Gossip protocol"
summary = "Spreading data by having each node forward new items to its peers, until everyone has them."
category = "Blockchain"
related = ["peer-to-peer", "peer-discovery"]
posts = ["bc-p2p-gossip"]
+++

A node that receives a new valid transaction or block relays it to every peer except the sender. A set of already-seen IDs stops the message from looping forever in a network with cycles.
