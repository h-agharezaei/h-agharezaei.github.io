+++
title = "Head-of-line blocking"
summary = "One slow item at the front of a queue holds up everything behind it."
category = "Networking"
related = ["multiplexing", "tcp"]
posts = ["net-http2"]
+++

In HTTP/1.1 one connection handles one response at a time, so a slow response blocks the next ones. HTTP/2 removes this at the HTTP level, but TCP still delivers bytes in order, so a lost packet can stall every stream on the connection.
