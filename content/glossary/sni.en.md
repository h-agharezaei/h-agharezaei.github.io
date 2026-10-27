+++
title = "SNI"
summary = "Server Name Indication: the client names the host it wants inside the TLS handshake."
category = "Networking"
related = ["tls"]
posts = ["net-tls-openssl"]
+++

One IP and port can serve many sites. SNI lets the client say `example.com` in the ClientHello, before any HTTP, so the server can choose the matching certificate.
