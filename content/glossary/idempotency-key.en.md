+++
title = "Idempotency key"
summary = "A unique id the client sends with a request so the server can recognise a retry and return the first result instead of acting twice."
category = "Distributed"
related = ["idempotency","at-least-once-delivery"]
posts = ["ds-capstone"]
+++

The server stores the key with the result of the first execution. A request that arrives again with the same key (a retry after a timeout, a double click) gets the stored answer and changes nothing. See [idempotency](/glossary/idempotency/).
