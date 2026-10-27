+++
title = "CORS"
summary = "Cross-Origin Resource Sharing: headers that tell a browser whether a page from another origin may read a response."
category = "Security"
related = ["preflight", "csrf"]
posts = ["sec-csrf-cors-headers"]
+++

It is enforced by the browser, not the server: the request still reaches the server. It controls reading, so it is not a CSRF defense.
