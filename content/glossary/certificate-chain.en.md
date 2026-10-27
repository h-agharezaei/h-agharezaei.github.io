+++
title = "Certificate chain"
summary = "The list leaf, intermediate(s), root that links a server certificate to a trusted root CA."
category = "Security"
related = ["certificate-authority", "x509-certificate"]
posts = ["sec-tls-x509-certificates"]
+++

A server certificate is usually signed by an intermediate CA, which is signed by a root the client trusts. The server must send the leaf and the intermediates; the root comes from the client's trust store. A missing intermediate causes a verification failure.

See [certificate authority](/glossary/certificate-authority/).
