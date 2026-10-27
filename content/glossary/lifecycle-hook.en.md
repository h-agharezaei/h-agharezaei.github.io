+++
title = "Lifecycle hook"
summary = "A function the framework calls at a fixed stage of a request, such as before the handler runs."
category = "Node.js"
related = ["json-schema"]
posts = ["node-fastify-api"]
+++

In Fastify the stages run in a fixed order: `onRequest`, `preValidation`, `preHandler`, the handler, then `onSend`. Hooks are the place for cross-cutting work such as request IDs or headers.
