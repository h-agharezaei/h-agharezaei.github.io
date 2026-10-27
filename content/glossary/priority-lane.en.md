+++
title = "Priority lane"
summary = "A separate queue or consumer per priority, served in strict order so urgent messages never wait behind a backlog."
category = "Distributed"
related = ["jetstream", "fan-out"]
posts = ["ds-case-studies"]
+++

Messages go to subjects such as `notify.high.sms` and `notify.low.sms`, and the worker asks the high consumer first. The risk is starvation of the low lane, so keep a share of capacity for it.
