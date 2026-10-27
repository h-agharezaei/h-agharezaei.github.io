+++
title = "Listen backlog"
summary = "The size of the kernel queue of connections waiting for accept()."
category = "Networking"
related = ["tcp", "socket"]
posts = ["net-tcp-handshake-states", "linux-networking-ip-ss-nftables"]
+++

`listen(fd, n)` gives the kernel a queue for connections that completed the handshake but were not yet taken by `accept()`. What happens when it is full (drop the SYN, reset, refuse) depends on the operating system.
