+++
title = "SubjectAltName (SAN)"
summary = "The certificate extension that lists the DNS names and IPs it is valid for."
category = "Networking"
related = ["x509-certificate", "tls"]
posts = ["net-tls-openssl"]
+++

Modern clients match the host name only against the SAN list (DNS names and IP addresses). The Common Name field alone is no longer enough for them; Go, for example, rejects such a certificate.
