+++
title = "Blue/green deployment"
summary = "Two identical releases side by side; traffic switches from the live one to the new one only after it is healthy."
category = "Engineering"
related = ["rollback", "health-check", "canary-release"]
posts = ["eng-ci-cd-pipeline-design", "ds-deployment-strategies"]
+++

The switch is one cheap step (a symlink, a load balancer target), so going back is the same step in reverse. The price is running two copies and handling a database both versions can use.
