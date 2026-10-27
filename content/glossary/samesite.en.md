+++
title = "SameSite"
summary = "A cookie attribute that limits when the browser sends the cookie on cross-site requests."
category = "Security"
related = ["csrf", "httponly"]
posts = ["sec-sessions-vs-jwt", "sec-csrf-cors-headers"]
+++

`Lax` skips the cookie on cross-site POSTs and sub-requests but sends it on normal top-level navigation; `Strict` is tighter; `None` needs `Secure`.
