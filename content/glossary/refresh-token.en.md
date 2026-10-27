+++
title = "Refresh token"
summary = "A long-lived credential that the client exchanges for a new short-lived access token."
category = "Security"
related = ["oauth2", "bearer-token"]
posts = ["sec-oauth2-oidc"]
+++

With rotation every use returns a new refresh token and invalidates the old one. If an old one shows up again, the server can treat it as theft and revoke the whole family.
