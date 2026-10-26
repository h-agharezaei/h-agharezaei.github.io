+++
title = "EventEmitter"
summary = "Node's built-in publish/subscribe object: emit named events, listeners react."
category = "Node.js"
related = ["unhandled-rejection"]
posts = ["node-errors-unhandled-rejections"]
+++

Most Node.js I/O objects (servers, streams) are EventEmitters. The special event name `error` is different: emitting it with no listener throws the error and can crash the process.
