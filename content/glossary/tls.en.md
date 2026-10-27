+++
title = "TLS"
summary = "Transport Layer Security: encrypts and authenticates a connection on top of TCP."
category = "Networking"
related = ["x509-certificate", "certificate-authority", "sni", "alpn", "mutual-tls"]
posts = ["net-tls-openssl", "net-load-balancer-l4-l7", "net-slow-request-case-study"]
+++

TLS (Transport Layer Security) sits between TCP and the application protocol. After a handshake the two sides share keys, the client has checked the server's certificate, and all data is encrypted and tamper-evident. HTTPS is HTTP over TLS.
