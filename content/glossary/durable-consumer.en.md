+++
title = "Durable consumer"
summary = "A named JetStream consumer whose position survives restarts and reconnects."
category = "Messaging"
related = ["jetstream", "idempotency"]
posts = ["nats-jetstream-go", "nats-jetstream-scaling-lag"]
+++

Because the server remembers which messages were acknowledged, a durable consumer resumes exactly where it stopped. Several instances can share the same durable name to split the work, which is how consumers scale horizontally.
