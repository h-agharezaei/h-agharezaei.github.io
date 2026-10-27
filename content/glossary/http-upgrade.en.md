+++
title = "HTTP Upgrade"
summary = "A request header that asks the server to switch the connection to another protocol (101 Switching Protocols)."
category = "Networking"
related = ["http", "websocket"]
posts = ["net-websocket"]
+++

The client sends `Upgrade: websocket` and `Connection: Upgrade`. If the server agrees it replies `101 Switching Protocols` and from then on the bytes on that connection are no longer HTTP.
