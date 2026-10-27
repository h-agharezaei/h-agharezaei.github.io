+++
title = "Structured logging"
summary = "Writing each log line as a JSON object with named fields instead of free text."
category = "Node.js"
related = ["request-id"]
posts = ["node-fastify-api", "eng-postmortems-blameless", "linux-logs-journalctl", "sec-logging-audit-incident-response"]
+++

Fields like `level`, `reqId` and `res.statusCode` can be filtered by tools without regular expressions. Pino, the logger inside Fastify, writes one JSON object per line.
