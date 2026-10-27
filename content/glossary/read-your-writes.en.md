+++
title = "Read-your-writes"
summary = "After a client writes a value, its own later reads see that value or a newer one."
category = "Distributed"
related = ["monotonic-reads","linearizability"]
posts = ["ds-consistency-models"]
+++

A session guarantee. A common fix is a session token holding the version the client last wrote; a replica that is behind it is skipped and the read goes to the leader.
