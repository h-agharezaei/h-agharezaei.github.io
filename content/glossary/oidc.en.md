+++
title = "OpenID Connect (OIDC)"
summary = "A thin identity layer on top of OAuth 2.0 that adds an ID token and a userinfo endpoint to tell the client who logged in."
category = "Security"
related = ["oauth2", "jwks", "jwt"]
posts = ["sec-oauth2-oidc"]
+++

OAuth2 alone says what a token may do; OIDC adds authentication. The client must validate the ID token: signature, `iss`, `aud`, `exp` and `nonce`.
