+++
title = "Publish-subscribe"
summary = "A messaging style where publishers send messages to a named subject and every subscriber of that subject gets its own copy."
category = "Distributed"
related = ["queue-group", "event-envelope"]
posts = ["ds-messaging-event-driven"]
+++

The publisher does not know who is listening, and a subscriber does not know who published. If three subscribers listen on one subject, each of them receives every message. Contrast this with a [queue group](/glossary/queue-group/), where the members share the messages instead.
