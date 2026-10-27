+++
title = "Clock skew"
summary = "The difference between the clocks of two machines at the same real moment."
category = "Distributed"
related = ["last-write-wins", "monotonic-clock"]
posts = ["ds-why-distributed-is-hard", "ds-logical-clocks"]
+++

Even with time synchronisation, machine clocks differ a little and sometimes a lot. Any rule that orders events by comparing timestamps from different machines inherits that error.
