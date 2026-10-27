+++
title = "AckWait"
summary = "How long JetStream waits for an ack before it redelivers a message."
category = "Messaging"
related = ["jetstream", "durable-consumer"]
posts = ["node-nats-jetstream"]
+++

If the consumer does not ack, nak or term within the AckWait, the server sends the message again, up to `max_deliver` times. A `backoff` list can replace the single value with growing delays.
