+++
title = "Load balancer"
summary = "A component that spreads incoming traffic across several backend servers."
category = "Networking"
related = ["reverse-proxy", "health-check"]
posts = ["net-load-balancer-l4-l7"]
+++

A load balancer sits in front of several identical backends and picks one for each connection (layer 4) or each request (layer 7). It also hides backends that are down.
