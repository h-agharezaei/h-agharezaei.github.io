+++
title = "traceroute"
summary = "Lists the routers on the path to a host by sending packets with a growing TTL."
category = "Networking"
related = ["ttl", "icmp"]
posts = ["net-troubleshooting-curl-traceroute"]
+++

A tool that sends packets whose TTL (hop limit) starts at 1 and grows. Each router that drops a packet because the TTL reached zero answers with an ICMP message, which reveals that hop. See [TTL](/glossary/ttl/) and [ICMP](/glossary/icmp/).
