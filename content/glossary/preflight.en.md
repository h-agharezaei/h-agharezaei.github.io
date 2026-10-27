+++
title = "Preflight request"
summary = "An OPTIONS request a browser sends first to ask whether a cross-origin request with a custom method or header is allowed."
category = "Security"
related = ["cors"]
posts = ["sec-csrf-cors-headers"]
+++

The server answers with `Access-Control-Allow-*` headers; `Access-Control-Max-Age` lets the browser cache the answer.
