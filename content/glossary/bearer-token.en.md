+++
title = "Bearer token"
summary = "A token that grants access to whoever holds it, sent as `Authorization: Bearer <token>`."
category = "Security"
related = ["oauth2", "refresh-token"]
posts = ["sec-oauth2-oidc"]
+++

Because holding it is enough, send it only over TLS, keep it out of URLs and logs, and keep its lifetime short.
