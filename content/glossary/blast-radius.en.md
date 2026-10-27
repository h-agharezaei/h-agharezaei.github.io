+++
title = "Blast radius"
summary = "how many users or requests a bad change can hurt."
category = "Distributed"
related = ["canary-release", "feature-flag"]
posts = ["ds-deployment-strategies", "ds-fault-injection-testing"]
+++

The blast radius is the part of the system or traffic affected when a change goes wrong. Canary releases, cells and feature flags exist mainly to make it small. You can measure it as the number of requests served by the bad version.
