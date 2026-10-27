+++
title = "Request smuggling"
summary = "An attack that exploits two HTTP parsers disagreeing about where a request ends."
category = "Networking"
related = ["http", "chunked-encoding"]
posts = ["net-http1-by-hand"]
+++

It becomes possible when, for example, a proxy and a backend disagree on whether `Content-Length` or `Transfer-Encoding` decides the body length. This is only a concept here; the security series will cover defences.
