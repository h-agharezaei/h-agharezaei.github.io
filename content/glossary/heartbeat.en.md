+++
title = "Heartbeat"
summary = "A periodic small message (such as a ping) used to find out whether the other side is still alive."
category = "Networking"
related = ["websocket", "deadline"]
posts = ["net-websocket", "ds-why-distributed-is-hard", "ds-service-discovery-load-balancing"]
+++

A half-dead TCP connection can look open for a long time. If a ping gets no pong before a deadline, the peer is treated as gone and the connection is closed.
