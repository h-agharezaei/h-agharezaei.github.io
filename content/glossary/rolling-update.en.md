+++
title = "Rolling update"
summary = "a deploy that replaces instances one by one."
category = "Distributed"
related = ["blue-green-deployment", "canary-release", "health-check"]
posts = ["ds-deployment-strategies"]
+++

A rolling update replaces the old version instance by instance, usually waiting for a readiness check before moving on. Old and new versions serve traffic together while it runs.
