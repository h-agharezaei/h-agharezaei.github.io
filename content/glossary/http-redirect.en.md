+++
title = "HTTP redirect"
summary = "A 3xx response with a Location header telling the client to request another URL."
category = "Networking"
related = ["http"]
posts = ["net-troubleshooting-curl-traceroute"]
+++

A redirect is a response such as 301 or 302 with a `Location` header. The client must send a new request to that URL; curl only does so with `-L`. See [HTTP](/glossary/http/).
