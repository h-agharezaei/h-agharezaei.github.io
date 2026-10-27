+++
title = "Distributed monolith"
summary = "Services split over the network that still have to change, deploy and fail together."
category = "Distributed"
related = ["microservices", "modular-monolith"]
posts = ["ds-modular-monolith-vs-microservices"]
+++

A distributed monolith has the costs of microservices without the benefits. Typical symptoms: deploys in lockstep, a shared database, and chatty calls where one request fans out into many. It usually means the boundaries were drawn before they were understood.
