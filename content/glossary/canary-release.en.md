+++
title = "Canary release"
summary = "exposing a change to a small share of traffic first."
category = "Engineering"
related = ["feature-flag"]
posts = ["eng-feature-flags-trunk-based", "eng-ci-cd-pipeline-design", "ds-deployment-strategies"]
+++

In a canary release a new version or code path serves a small percentage of users while you watch errors and metrics. If it looks healthy the share grows; if not, you stop and roll back. Percentage rollout with a feature flag is one way to do it.
