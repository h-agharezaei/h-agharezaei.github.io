+++
title = "Lamport clock"
summary = "A single counter per process, advanced on events and merged with max on receive, so that a happens-before b implies a smaller timestamp."
category = "Distributed"
related = ["happens-before", "vector-clock"]
posts = ["ds-logical-clocks"]
+++

The converse does not hold: a smaller timestamp does not mean happens-before, so a Lamport clock cannot detect concurrency. Ties are often broken by process id to get a total order.
