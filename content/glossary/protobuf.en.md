+++
title = "Protocol Buffers"
summary = "A compact binary format for structured messages, described in .proto files."
category = "Networking"
related = ["grpc"]
posts = ["net-grpc-over-http2"]
+++

Protocol Buffers (protobuf) encode a message as a list of field number and value pairs, not field names, so messages are small and tolerant of added fields. [gRPC](/glossary/grpc/) uses it as its default message format.
