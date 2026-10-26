+++
title = "Unhandled rejection"
summary = "A rejected promise that nobody handled with catch or try/catch."
category = "Node.js"
related = ["promise"]
posts = ["node-promises-async-await", "node-http-server"]
+++

Since Node 15 the default is to crash the process with exit code 1 (checked here on Node 20). Always handle or return the [promise](/glossary/promise/).
