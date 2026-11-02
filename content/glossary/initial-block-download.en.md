+++
title = "Initial block download (IBD)"
summary = "The phase in which a new or long-offline node downloads and validates the chain until it reaches the network's tip."
category = "Blockchain"
related = ["full-node", "peer-discovery"]
posts = ["bc-toy-node-go"]
+++

Bitcoin Core downloads headers first, checks their proof of work, and then fetches block bodies from several peers in parallel.
