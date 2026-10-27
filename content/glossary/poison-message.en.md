+++
title = "Poison message"
summary = "A message that makes its consumer fail every time, so redelivery never succeeds."
category = "Distributed"
related = ["dlq", "at-least-once-delivery"]
posts = ["ds-messaging-event-driven"]
+++

Without a delivery limit it blocks or loops forever; the usual fix is a max-deliver count and a dead-letter destination.
