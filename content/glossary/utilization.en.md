+++
title = "Utilization"
summary = "The fraction of time a server is busy: arrival rate divided by service rate."
category = "Distributed"
related = ["littles-law", "tail-latency"]
posts = ["ds-capacity-estimation"]
+++

In a simple queue the waiting time grows like 1/(1-ρ), so latency explodes as utilization ρ nears 100%. That is why capacity plans target 50-70%, not 95%.
