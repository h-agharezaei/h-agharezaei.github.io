+++
title = "JWKS"
summary = "A JSON document, usually at /jwks.json, that publishes the public keys used to verify an issuer's signed tokens."
category = "Security"
related = ["oidc", "jwt"]
posts = ["sec-oauth2-oidc"]
+++

Each key has a `kid` that the token header names, which makes key rotation possible without changing the clients.
