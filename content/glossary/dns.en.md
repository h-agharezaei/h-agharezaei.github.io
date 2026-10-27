+++
title = "DNS"
summary = "The system that maps names to records such as IP addresses."
category = "Networking"
related = ["recursive-resolver", "authoritative-server", "ttl"]
posts = ["net-dns-in-practice", "net-troubleshooting-curl-traceroute", "ds-service-discovery-load-balancing"]
+++

DNS is a distributed, hierarchical database: the root delegates to top-level domains, which delegate to each domain's own name servers. Clients ask it for records (A, AAAA, MX, TXT...) by name.
