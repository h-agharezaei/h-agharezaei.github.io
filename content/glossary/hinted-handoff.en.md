+++
title = "Hinted handoff"
summary = "When a replica is down, another node holds its writes with a hint and hands them over when it returns."
category = "Distributed"
related = ["quorum", "replication"]
posts = ["ds-replication-quorum"]
+++

It keeps writes succeeding during short outages. The hinted node is not one of the key's real replicas, so this is called a sloppy quorum and it weakens the overlap guarantee of [quorum](/glossary/quorum/).
