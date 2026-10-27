+++
title = "Two-phase commit (2PC)"
summary = "A protocol where a coordinator asks all participants to prepare, then tells them all to commit or all to abort."
category = "Distributed"
related = ["saga", "prepared-transaction", "atomic-commit"]
posts = ["ds-saga-vs-2pc"]
+++

In phase one every participant makes its work durable and votes yes or no. In phase two the coordinator, having logged its decision, tells all to commit or abort. It gives atomicity across systems, but a prepared participant must wait for the coordinator and keeps its locks meanwhile.
