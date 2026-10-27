+++
title = "HTTP"
summary = "A text protocol for requests and responses, usually carried over TCP."
category = "Networking"
related = ["tcp", "message-framing"]
posts = ["net-http1-by-hand", "net-websocket", "net-grpc-over-http2", "net-troubleshooting-curl-traceroute"]
+++

HTTP/1.1 is a text protocol: a request line, header lines, a blank line and an optional body, all separated by CRLF. The server answers with a status line, headers, a blank line and a body.
