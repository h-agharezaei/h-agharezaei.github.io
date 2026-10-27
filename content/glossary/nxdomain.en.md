+++
title = "NXDOMAIN"
summary = "The DNS response code meaning that the name does not exist."
category = "Networking"
related = ["dns", "ttl"]
posts = ["net-dns-in-practice", "net-troubleshooting-curl-traceroute"]
+++

NXDOMAIN is RCODE 3. It differs from NOERROR with an empty answer, which means the name exists but has no record of the asked type. Resolvers cache negative answers too.
