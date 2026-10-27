+++
title = "Hysteresis"
summary = "Requiring several consecutive probes before changing state, so a flapping instance does not flip in and out of rotation."
category = "Distributed"
related = ["health-check", "circuit-breaker"]
posts = ["ds-service-discovery-load-balancing"]
+++

The price is a slower reaction: ejecting a really dead instance takes as many probes as the threshold.
