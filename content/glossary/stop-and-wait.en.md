+++
title = "Stop-and-wait"
summary = "A reliability scheme: send one packet, wait for its acknowledgement, resend on timeout."
category = "Networking"
related = ["udp", "datagram"]
posts = ["net-udp-sockets"]
+++

A reliability scheme: send one packet, wait for its acknowledgement, resend on timeout. It needs a sequence number so the receiver can spot duplicates. It is simple but sends only one packet per round trip.
