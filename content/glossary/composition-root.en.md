+++
title = "Composition root"
summary = "The single place (usually `main`) where concrete parts are created and wired together."
category = "Node.js"
related = ["dependency-injection", "environment-variable"]
posts = ["node-project-structure-config"]
+++

The single place (usually `main`) where concrete parts are created and wired together. Everything else receives its dependencies as arguments, so tests can pass fakes. No DI framework is required.
