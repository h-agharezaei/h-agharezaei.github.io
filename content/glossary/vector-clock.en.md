+++
title = "Vector clock"
summary = "One counter per process; comparing two vectors tells before, after or concurrent exactly."
category = "Distributed"
related = ["happens-before", "lamport-clock", "version-vector"]
posts = ["ds-logical-clocks"]
+++

Each process increments its own slot and takes the element-wise max on receive. The price is a vector as large as the number of participants.
