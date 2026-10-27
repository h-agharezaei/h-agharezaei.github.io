+++
title = "IDOR"
summary = "Insecure direct object reference: an endpoint returns an object by its ID without checking that the caller may see it."
category = "Security"
related = ["owasp-top-10"]
posts = ["sec-owasp-top10-in-code", "sec-authorization-rbac-idor"]
+++

Example: `GET /orders/2` returns bob's order to alice. The fix is an ownership check on the server for every read.
