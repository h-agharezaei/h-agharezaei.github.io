+++
title = "gRPC"
summary = "A binary RPC framework built on HTTP/2 and Protocol Buffers."
category = "Go"
related = ["ffi"]
posts = ["go-grpc-service", "go-rust-grpc-interop", "net-grpc-over-http2"]
+++

Services and messages are described in `.proto` files, from which client and server code is generated in many languages, which makes it a good fit for Go↔Rust communication. It supports unary calls and client, server and bidirectional streaming.
