+++
title = "Domain event"
summary = "A fact that happened in the domain, named in the past tense, such as OrderPlaced."
category = "Engineering"
related = ["aggregate", "outbox-pattern"]
posts = ["eng-ddd-basics"]
+++

The aggregate collects events while it changes; the application service publishes them only after the save succeeds (see the [outbox](/glossary/outbox-pattern/) pattern for doing that reliably).
