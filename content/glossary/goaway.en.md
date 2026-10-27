+++
title = "GOAWAY"
summary = "An HTTP/2 frame that tells the peer to stop opening new streams on this connection."
category = "Networking"
related = ["multiplexing", "graceful-shutdown"]
posts = ["net-grpc-over-http2"]
+++

A GOAWAY frame carries the id of the last stream the sender will process. Streams up to that id may finish; later ones must be retried on another connection. It is how an HTTP/2 or gRPC server drains a connection before closing it.
