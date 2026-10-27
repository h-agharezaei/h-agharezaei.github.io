+++
title = "Audit log"
summary = "A tamper-evident record of who did what to which object, when, from where, and with what result."
category = "Security"
related = ["hash-chain", "structured-logging"]
posts = ["sec-logging-audit-incident-response"]
+++

An audit log answers legal and forensic questions, not debugging ones. Each record names an actor, an action, a resource, an outcome, a request id, a source address and a UTC timestamp. It is append-only and ideally kept off the machine that writes it.
