+++
title = "Power of two choices"
summary = "Load balancing rule: pick two random instances and send the request to the one with the shorter queue."
category = "Distributed"
related = ["load-balancer", "service-discovery"]
posts = ["ds-service-discovery-load-balancing"]
+++

It needs only two load readings per request, yet in a simulation (see the post) it stays close to always picking the least loaded instance and far better than random.
