+++
title = "CSRF"
summary = "Cross-site request forgery: another site makes the browser send an authenticated request you did not intend."
category = "Security"
related = ["session", "samesite", "httponly"]
posts = ["sec-sessions-vs-jwt", "sec-oauth2-oidc", "sec-csrf-cors-headers"]
+++

It works because browsers attach cookies automatically. Defences: SameSite cookies and a per-session token that must be sent in a header or form field.
