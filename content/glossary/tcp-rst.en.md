+++
title = "RST"
summary = "A TCP segment that aborts a connection immediately, without the orderly FIN exchange."
category = "Networking"
related = ["tcp", "half-close"]
posts = ["net-tcp-handshake-states"]
+++

FIN says "I am done sending" and is delivered in order; RST says "this connection is dead". The peer sees `ECONNRESET`, and a connect to a closed port on loopback is answered with RST (`connection refused`).
