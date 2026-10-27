+++
title = "Authorization Code flow"
summary = "The OAuth2 flow where the browser carries only a short-lived code and the client swaps it for tokens on a back channel."
category = "Security"
related = ["oauth2", "pkce"]
posts = ["sec-oauth2-oidc"]
+++

Tokens never travel through the URL. Current guidance recommends it, with PKCE, for all clients.
