+++
title = "HttpOnly"
summary = "A cookie attribute that hides the cookie from JavaScript running in the page."
category = "Security"
related = ["xss"]
posts = ["sec-injection-xss"]
+++

The browser still sends the cookie with requests, but `document.cookie` cannot read it, so an XSS bug cannot simply steal a session cookie.
