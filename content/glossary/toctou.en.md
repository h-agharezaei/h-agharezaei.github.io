+++
title = "TOCTOU"
summary = "Time-of-check to time-of-use: the state changes between the check and the action that relied on it."
category = "Security"
related = ["race-condition", "dns-rebinding"]
posts = ["sec-ssrf-deserialization"]
+++

You check a condition and act later, but something else can change it in between. The fix is to make check and use one atomic step, or to act on the thing you checked. See [race condition](/glossary/race-condition/).
