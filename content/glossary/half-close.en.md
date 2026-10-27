+++
title = "Half-close"
summary = "Closing only the sending direction of a TCP connection while still reading."
category = "Networking"
related = ["tcp", "socket"]
posts = ["net-sockets-tcp-from-scratch", "net-tcp-handshake-states"]
+++

A TCP connection has two independent directions. A half-close (`shutdown(SHUT_WR)`, `CloseWrite` in Go) tells the peer "I am done sending" (it sees EOF) while you can still read its answer.
