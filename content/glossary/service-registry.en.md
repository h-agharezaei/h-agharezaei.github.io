+++
title = "Service registry"
summary = "A small service that stores which instances are alive; instances register with a TTL and keep renewing it."
category = "Distributed"
related = ["service-discovery", "ttl", "heartbeat"]
posts = ["ds-service-discovery-load-balancing"]
+++

If an instance stops renewing, its entry expires after the [TTL](/glossary/ttl/). Between the crash and the expiry the registry is stale.
