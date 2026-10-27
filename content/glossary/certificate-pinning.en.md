+++
title = "Certificate pinning"
summary = "Accepting only a server whose certificate or public key matches a hash the client already knows."
category = "Security"
related = ["tls", "x509-certificate"]
posts = ["sec-tls-x509-certificates"]
+++

The client stores the SHA-256 hash of the server's public key (SPKI) and rejects any other key, even if a trusted CA signed it. It limits the damage of a wrongly issued certificate but makes rotation harder, so pin carefully and keep a backup pin.
