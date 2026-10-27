+++
title = "Modular monolith"
summary = "One deployable whose modules talk only through narrow interfaces."
category = "Distributed"
related = ["microservices", "distributed-monolith"]
posts = ["ds-modular-monolith-vs-microservices"]
+++

A modular monolith is deployed as one program, but split into modules with clear boundaries. Each module exposes a small interface and hides the rest; other modules may only use that interface. You keep one process and one transaction, and you keep the option to extract a module later.
