+++
title = "Request ID"
summary = "A unique identifier attached to one request and to every log line it produces."
category = "Node.js"
related = ["structured-logging"]
posts = ["node-fastify-api"]
+++

With a request ID you can pull every log line of one request out of a busy log. It is often accepted from an incoming header (such as `x-request-id`) and returned to the caller so both sides can quote it.
