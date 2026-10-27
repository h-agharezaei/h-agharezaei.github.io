+++
title = "Jitter"
summary = "Randomness added to a retry delay so clients stop retrying in lockstep."
category = "Distributed"
related = ["exponential-backoff", "retry-storm"]
posts = ["ds-timeouts-retries-backoff"]
+++

Full jitter picks the delay uniformly in `[0, backoff]`; equal jitter keeps half the backoff and randomises the rest. Both spread the retries of many clients over time. See [exponential backoff](/glossary/exponential-backoff/).
