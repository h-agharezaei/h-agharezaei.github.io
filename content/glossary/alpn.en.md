+++
title = "ALPN"
summary = "Application-Layer Protocol Negotiation: TLS picks the protocol, such as h2 or http/1.1."
category = "Networking"
related = ["tls", "sni"]
posts = ["net-tls-openssl", "net-http2"]
+++

In the handshake the client lists protocols (`h2`, `http/1.1`) and the server picks one. That is how HTTPS decides between HTTP/2 and HTTP/1.1 without an extra round trip.
