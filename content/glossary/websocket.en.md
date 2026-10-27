+++
title = "WebSocket"
summary = "A protocol for a persistent two-way message channel, started by an HTTP upgrade."
category = "Networking"
related = ["http", "http-upgrade", "message-framing"]
posts = ["net-websocket"]
+++

After an HTTP handshake the same TCP connection carries small frames in both directions, so the server can push without being asked. It is defined in RFC 6455.
