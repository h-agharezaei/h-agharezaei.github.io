+++
title = "PKCE"
summary = "Proof Key for Code Exchange: the client proves at the token request that it is the one that started the authorization request."
category = "Security"
related = ["oauth2", "authorization-code-flow"]
posts = ["sec-oauth2-oidc"]
+++

The client makes a random verifier, sends its SHA-256 (the challenge) in the authorization request and the verifier itself in the token request. A stolen code is useless without the verifier.
