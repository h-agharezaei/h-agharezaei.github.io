+++
title = "Monotonic reads"
summary = "A client's successive reads never go back to an older value."
category = "Distributed"
related = ["read-your-writes","eventual-consistency"]
posts = ["ds-consistency-models"]
+++

It can break when consecutive reads hit different replicas with different lag. Pinning the client to one replica, or a session token, prevents it.
