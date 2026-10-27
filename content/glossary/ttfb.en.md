+++
title = "TTFB"
summary = "Time to first byte: how long until the first byte of the response arrives."
category = "Networking"
related = ["http", "tls"]
posts = ["net-slow-request-case-study"]
+++

TTFB is the time from sending a request to receiving the first byte of the response. A large TTFB usually means the server was busy thinking; a large time after it means the body was slow. Tools measure it from different starting points, so say which one you use.
