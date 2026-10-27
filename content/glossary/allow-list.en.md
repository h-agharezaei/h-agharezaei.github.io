+++
title = "Allow-list"
summary = "A list of the only values accepted, with everything else rejected by default."
category = "Security"
related = ["ssrf"]
posts = ["sec-ssrf-deserialization"]
+++

Safer than a block-list, which tries to name every bad value and always misses one. Typical examples are allowed URL schemes, ports and destination hosts.
