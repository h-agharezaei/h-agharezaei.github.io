+++
title = "Microservices"
summary = "Independently deployed services that each own their data and talk over the network."
category = "Distributed"
related = ["modular-monolith", "distributed-monolith", "conways-law"]
posts = []
+++

In a microservice architecture the system is many small services, each deployed on its own and owning its own data. The gain is independent deploy, scaling and failure isolation. The price is that every call is now a network call that can be slow, lost or duplicated.
