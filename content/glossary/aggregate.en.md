+++
title = "Aggregate"
summary = "A cluster of objects changed as one unit, with a root that enforces its rules."
category = "Engineering"
related = ["value-object", "domain-event", "transaction"]
posts = ["eng-ddd-basics"]
+++

Outside code talks only to the aggregate root. Other aggregates are referenced by ID, and one [transaction](/glossary/transaction/) changes one aggregate.
