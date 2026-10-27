+++
title = "Message framing"
summary = "Rules that mark where one message ends in a byte stream such as TCP."
category = "Networking"
related = ["tcp", "stream"]
posts = ["net-sockets-tcp-from-scratch", "net-udp-sockets", "net-http1-by-hand", "net-grpc-over-http2"]
+++

TCP gives you bytes without boundaries, so the protocol must say where a message ends. Two common ways: a delimiter such as a newline, or a length prefix (a fixed-size number before the payload). See [stream](/glossary/stream/).
