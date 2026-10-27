+++
title = "JWT"
summary = "A signed token (header.payload.signature, base64url) carrying claims; signed, not encrypted."
category = "Security"
related = ["session", "csrf"]
posts = ["sec-sessions-vs-jwt", "sec-oauth2-oidc"]
+++

Anyone can read the payload; only the signature stops changes. It is valid until its `exp` unless the server keeps extra state.
