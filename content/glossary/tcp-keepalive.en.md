+++
title = "TCP keepalive"
summary = "Probe packets the kernel sends on an idle connection to detect a dead peer."
category = "Networking"
related = ["tcp", "socket"]
posts = ["net-tcp-handshake-states"]
+++

With `SO_KEEPALIVE` on, the kernel sends small probes after the connection has been idle for a while. If the peer never answers, the connection is closed with an error. It is different from HTTP keep-alive, which is about reusing a connection.
