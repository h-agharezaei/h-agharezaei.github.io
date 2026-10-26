+++
title = "Denormalization"
summary = "Deliberately storing a fact more than once to make reads cheaper."
category = "Databases"
related = ["normalization"]
posts = ["db-schema-design-normalization"]
+++

Denormalization means deliberately keeping a copy of data in more than one place, for example a stored order total, to avoid expensive joins or aggregates. The price is that you must keep the copies in sync. It is a decision you make after [normalizing](/glossary/normalization/), not instead of it.
