+++
title = "UDP"
summary = "A connectionless datagram protocol on top of IP, with no delivery guarantee."
category = "Networking"
related = ["tcp", "dns"]
posts = ["net-dns-in-practice"]
+++

UDP sends independent datagrams with just a port and a checksum added to IP. Nothing is retransmitted for you, so the application handles loss, which suits small request/response protocols such as DNS.
