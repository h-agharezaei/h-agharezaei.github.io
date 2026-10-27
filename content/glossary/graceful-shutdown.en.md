+++
title = "Graceful shutdown"
summary = "Stopping a server by refusing new work but letting in-flight requests finish before exiting."
category = "Node.js"
related = ["keep-alive"]
posts = ["node-http-server", "node-fastify-api", "node-nats-jetstream"]
+++

On a stop signal such as SIGTERM the process stops accepting new connections, closes idle ones, waits for requests already running, and only then exits with code 0. A timer usually forces exit if something never finishes.
