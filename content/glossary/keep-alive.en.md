+++
title = "Keep-alive"
summary = "Reusing one TCP connection for several HTTP requests instead of opening a new one each time."
category = "Node.js"
related = ["graceful-shutdown"]
posts = ["node-http-server", "net-http1-by-hand", "node-profiling-memory-shutdown", "net-load-balancer-l4-l7", "net-slow-request-case-study"]
+++

With HTTP keep-alive the connection stays open after a response so the next request can reuse it. The server closes it after an idle timeout (`keepAliveTimeout` in Node.js).
