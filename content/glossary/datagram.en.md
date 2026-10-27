+++
title = "Datagram"
summary = "A self-contained packet of data sent without a connection; it arrives whole or not at all."
category = "Networking"
related = ["udp", "stream"]
posts = ["net-udp-sockets"]
+++

A self-contained packet of data sent without a connection; it arrives whole or not at all. UDP sends one datagram per send call, and the receiver gets it with the same boundaries. Compare a TCP stream, which has no boundaries.
