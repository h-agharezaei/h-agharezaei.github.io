+++
title = "Node cluster"
summary = "The `cluster` module: several Node processes sharing one listening port."
category = "Node.js"
related = ["worker-threads", "event-loop"]
posts = ["node-worker-threads-cluster"]
+++

The `cluster` module lets a primary process fork worker processes that all accept connections on the same port. They share no memory. The primary decides how to distribute connections and what to do when a worker dies.
