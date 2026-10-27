+++
title = "Fail open"
summary = "Letting requests through when a protective component, such as the limiter store, is unavailable."
category = "Distributed"
related = ["rate-limiting", "lease"]
posts = []
+++

The opposite is fail closed, which rejects. Choose per endpoint: availability usually wins for cheap reads, safety for login or costly work.
