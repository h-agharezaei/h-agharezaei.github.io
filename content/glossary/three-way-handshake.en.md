+++
title = "Three-way handshake"
summary = "SYN, SYN-ACK, ACK: how TCP opens a connection."
category = "Networking"
related = ["tcp", "tcp-rst"]
posts = ["net-tcp-handshake-states"]
+++

The client sends a segment with the SYN flag, the server answers SYN+ACK, and the client confirms with ACK. Both sides now know each other's initial sequence numbers and the connection is ESTABLISHED.
