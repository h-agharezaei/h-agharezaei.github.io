+++
title = "Health check"
summary = "A probe that tells a load balancer whether a backend can take traffic."
category = "Networking"
related = ["load-balancer"]
posts = ["net-load-balancer-l4-l7"]
+++

An active check sends probes (for example `GET /healthz`) on a timer; a passive check watches real traffic for errors. After a few failures the backend leaves the rotation.
