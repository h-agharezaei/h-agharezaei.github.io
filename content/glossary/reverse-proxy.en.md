+++
title = "Reverse proxy"
summary = "A server that receives client requests and forwards them to backends on the client's behalf."
category = "Networking"
related = ["load-balancer"]
posts = ["net-load-balancer-l4-l7"]
+++

A reverse proxy terminates the client's HTTP connection, reads the request, and sends a new request to a backend. Because it understands HTTP it can route by path, add headers and retry.
