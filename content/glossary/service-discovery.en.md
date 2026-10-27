+++
title = "Service discovery"
summary = "Finding the current network addresses of the instances of a service while they come and go."
category = "Distributed"
related = ["service-registry", "load-balancer", "dns"]
posts = ["ds-service-discovery-load-balancing"]
+++

Instances start, crash and move, so addresses cannot be hard-coded. Clients ask DNS, a [registry](/glossary/service-registry/) or a message bus who is alive now.
