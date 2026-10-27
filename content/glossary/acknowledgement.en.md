+++
title = "Acknowledgement (ack)"
summary = "The consumer's reply to JetStream: ack (done), nak (retry), term (never retry)."
category = "Messaging"
related = ["jetstream", "durable-consumer"]
posts = ["node-nats-jetstream"]
+++

With explicit acks the server keeps a message as pending until the consumer answers. `ack` means done, `nak` asks for redelivery (optionally after a delay), and `term` tells the server to stop redelivering it.
