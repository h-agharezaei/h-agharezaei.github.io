+++
title = "DNS rebinding"
summary = "A name that resolves to a harmless address for the check and to an internal one for the connection."
category = "Security"
related = ["ssrf", "toctou", "dns"]
posts = ["sec-ssrf-deserialization"]
+++

If code validates the answer of one DNS lookup and then connects by name, a second lookup can return another address. The defense is to resolve once and connect to the validated IP. See [TOCTOU](/glossary/toctou/).
