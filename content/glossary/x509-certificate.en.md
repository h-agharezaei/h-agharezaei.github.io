+++
title = "X.509 certificate"
summary = "A signed document binding a public key to a name, with a validity period."
category = "Networking"
related = ["certificate-authority", "subject-alt-name", "tls"]
posts = ["net-tls-openssl"]
+++

An X.509 certificate contains a public key, the subject it belongs to, the issuer that signed it, a validity period (not before and not after) and extensions such as the SubjectAltName. `openssl x509 -text` prints all of it.
