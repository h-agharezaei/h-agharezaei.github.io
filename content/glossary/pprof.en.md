+++
title = "pprof"
summary = "Go's profiling tool and the `net/http/pprof` handlers that expose profiles over HTTP."
category = "Security"
related = ["loopback"]
posts = ["sec-owasp-top10-in-code"]
+++

Those endpoints reveal internals, so they belong on a loopback or admin listener, not on the public mux.
