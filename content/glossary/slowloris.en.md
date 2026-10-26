+++
title = "Slowloris"
summary = "A denial-of-service pattern where a client sends a request extremely slowly to hold server connections open."
category = "Node.js"
related = ["keep-alive"]
posts = ["node-http-server"]
+++

A slow client sends headers or body a few bytes at a time and never finishes, so each connection occupies server resources. Timeouts such as `headersTimeout` and `requestTimeout` are the main defence.
