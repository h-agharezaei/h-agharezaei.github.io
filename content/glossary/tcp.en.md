+++
title = "TCP"
summary = "A reliable, ordered byte-stream protocol on top of IP."
category = "Networking"
related = ["socket", "mss"]
posts = ["net-tcp-ip-model", "net-dns-in-practice", "net-sockets-tcp-from-scratch", "net-tcp-handshake-states", "net-udp-sockets", "net-http1-by-hand", "net-http2", "net-websocket", "net-grpc-over-http2", "net-load-balancer-l4-l7"]
+++

TCP numbers bytes, acknowledges them and retransmits lost ones, so the application sees a stream, not messages. Message boundaries are the application's job.
