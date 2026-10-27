+++
title = "HTTP trailers"
summary = "Header fields sent after the body, once the final result is known."
category = "Networking"
related = ["grpc", "multiplexing"]
posts = ["net-grpc-over-http2"]
+++

Trailers are a second block of headers that follows the message body. HTTP/2 allows them on any response. [gRPC](/glossary/grpc/) uses them to deliver `grpc-status` and `grpc-message`, because the outcome of a call is only known after the last message has been sent.
