+++
title = "Mutual TLS (mTLS)"
summary = "TLS where the client also presents a certificate and the server verifies it."
category = "Networking"
related = ["tls", "certificate-authority"]
posts = ["net-tls-openssl", "sec-tls-x509-certificates"]
+++

In normal TLS only the server proves who it is. In mutual TLS the server asks for a client certificate too and rejects the connection if it is missing or not signed by a trusted CA. It is common between internal services.
