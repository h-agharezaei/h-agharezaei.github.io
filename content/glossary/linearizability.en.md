+++
title = "Linearizability"
summary = "Every operation appears to take effect at one instant between its start and end, as if there were a single copy of the data."
category = "Distributed"
related = ["cap-theorem","quorum"]
posts = ["ds-cap-pacelc", "ds-consistency-models"]
+++

This is what the C in CAP means. A read that starts after a write has completed must see that write. See [CAP theorem](/glossary/cap-theorem/).
