+++
title = "HPACK"
summary = "The header compression scheme of HTTP/2."
category = "Networking"
related = ["multiplexing"]
posts = ["net-http2"]
+++

Client and server keep a table of headers already sent on the connection. A repeated header such as a long cookie is then sent as a small table index instead of the full text.
