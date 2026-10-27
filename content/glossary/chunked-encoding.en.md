+++
title = "Chunked encoding"
summary = "An HTTP/1.1 way to send a body in pieces without knowing its total length."
category = "Networking"
related = ["http", "message-framing"]
posts = ["net-http1-by-hand"]
+++

With `Transfer-Encoding: chunked` each piece is a hex size, CRLF, the data and CRLF. A chunk of size 0 ends the body.
