+++
title = "Tolerant reader"
summary = "A client that ignores fields it does not know, so additive API changes do not break it."
category = "Engineering"
related = ["semver"]
posts = ["eng-api-design-versioning-pagination", "ds-messaging-event-driven", "ds-deployment-strategies", "ds-modular-monolith-vs-microservices"]
+++

A tolerant reader takes only the fields it needs and ignores the rest. Adding a field to a response is then a safe, non-breaking change. A strict decoder that rejects unknown fields turns the same change into an outage.
