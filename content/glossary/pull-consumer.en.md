+++
title = "Pull consumer"
summary = "A JetStream consumer where the client asks for messages instead of the server pushing them."
category = "Messaging"
related = ["jetstream", "durable-consumer"]
posts = ["node-nats-jetstream"]
+++

The client requests a batch (or one message) and processes it at its own pace, so it is naturally protected from being overwhelmed. It is the recommended style for workers.
