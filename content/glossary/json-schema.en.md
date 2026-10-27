+++
title = "JSON Schema"
summary = "A vocabulary for describing the shape of a JSON document so a library can validate it automatically."
category = "Node.js"
related = ["structured-logging"]
posts = ["node-fastify-api"]
+++

A schema says things like "this is an object, `qty` is an integer of at least 1, `item` is required". Fastify compiles the schema once and uses it to reject bad input and to serialize output.
