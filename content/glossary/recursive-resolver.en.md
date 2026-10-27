+++
title = "Recursive resolver"
summary = "A DNS server that does the whole lookup for a client and caches the result."
category = "Networking"
related = ["authoritative-server", "dns", "ttl"]
posts = ["net-dns-in-practice", "net-troubleshooting-curl-traceroute"]
+++

Your program asks a recursive resolver (for example a public one or your ISP's). It walks from the root to the TLD to the authoritative server and returns the final answer, caching along the way.
