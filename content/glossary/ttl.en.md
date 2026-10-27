+++
title = "TTL"
summary = "How many seconds a cached record may be reused before asking again."
category = "Networking"
related = ["dns", "recursive-resolver"]
posts = ["net-dns-in-practice"]
+++

Each DNS record carries a TTL (time to live). A caching resolver counts it down, so repeated queries show smaller values until it expires and the resolver asks the authoritative server again.
