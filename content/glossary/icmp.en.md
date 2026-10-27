+++
title = "ICMP"
summary = "The control-message protocol of IP, used for errors such as port unreachable."
category = "Networking"
related = ["udp", "datagram"]
posts = ["net-udp-sockets"]
+++

The control-message protocol of IP, used for errors such as port unreachable. When a datagram reaches a host with nothing listening on that UDP port, the host may answer with an ICMP port-unreachable message.
