+++
title = "Multiplexing"
summary = "Sending many independent requests and responses at once over a single connection."
category = "Networking"
related = ["alpn", "head-of-line-blocking"]
posts = ["net-http2"]
+++

In HTTP/2 each request is a numbered stream, and frames of different streams are interleaved on one TCP connection. The client does not need one connection per in-flight request.
