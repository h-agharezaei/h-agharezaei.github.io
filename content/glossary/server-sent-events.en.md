+++
title = "Server-Sent Events"
summary = "A one-way, text-based stream of events from server to browser over a normal HTTP response."
category = "Networking"
related = ["http", "websocket"]
posts = ["net-websocket"]
+++

The server keeps a response open with `Content-Type: text/event-stream` and writes `data:` lines; the browser's `EventSource` reconnects by itself. The client cannot send messages on that channel.
