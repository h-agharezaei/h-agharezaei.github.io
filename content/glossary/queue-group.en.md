+++
title = "Queue group"
summary = "Subscribers that share a name so each message goes to only one member of the group."
category = "Distributed"
related = ["fan-out", "jetstream"]
posts = ["ds-messaging-event-driven", "ds-service-discovery-load-balancing"]
+++

In core NATS the server picks a member per message; subscribers outside the group still get their own copy.
