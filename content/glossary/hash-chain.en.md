+++
title = "Hash chain"
summary = "Each record stores the hash of the previous one, so any edit, deletion or reorder breaks every later link."
category = "Security"
related = ["audit-log", "hmac"]
posts = ["sec-logging-audit-incident-response"]
+++

A hash chain makes a log tamper-evident, not tamper-proof: someone who can rewrite the whole file can recompute the chain. Signed checkpoints stored elsewhere close that gap.
