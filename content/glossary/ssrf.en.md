+++
title = "SSRF"
summary = "Server-side request forgery: making the server fetch a URL chosen by the user, so it reaches places the user cannot."
category = "Security"
related = ["loopback", "owasp-top-10"]
posts = ["sec-owasp-top10-in-code", "sec-ssrf-deserialization"]
+++

Typical targets are internal services on loopback or a private network. An allow-list of hosts is the usual defense.
