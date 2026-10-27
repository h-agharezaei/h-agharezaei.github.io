+++
title = "OCSP"
summary = "A way to ask a CA whether a specific certificate has been revoked."
category = "Security"
related = ["certificate-authority", "x509-certificate"]
posts = ["sec-tls-x509-certificates"]
+++

Instead of downloading a whole revocation list, a client (or the server, via stapling) asks the CA about one serial number. I did not run this; as far as I know Go's standard TLS client does not check revocation by itself.
