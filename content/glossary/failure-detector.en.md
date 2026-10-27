+++
title = "Failure detector"
summary = "A component that guesses whether a remote node is down, usually from missing heartbeats within a timeout."
category = "Distributed"
related = ["heartbeat", "gray-failure", "partial-failure"]
posts = ["ds-why-distributed-is-hard"]
+++

In an asynchronous network it cannot be exact. A short timeout detects real crashes quickly but suspects healthy nodes; a long timeout does the opposite.
