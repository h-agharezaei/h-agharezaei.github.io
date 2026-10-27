+++
title = "Version vector"
summary = "A vector clock attached to a stored value so replicas can tell an update from a conflicting one."
category = "Distributed"
related = ["vector-clock", "last-write-wins"]
posts = ["ds-logical-clocks"]
+++

If one vector dominates the other, the older value is dropped; if they are concurrent, both are kept as siblings for the application to merge.
