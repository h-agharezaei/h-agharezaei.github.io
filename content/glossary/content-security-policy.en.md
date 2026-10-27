+++
title = "Content Security Policy"
summary = "A response header that tells the browser which sources of scripts and other content a page may use."
category = "Security"
related = ["xss"]
posts = ["sec-injection-xss", "sec-csrf-cors-headers"]
+++

For example `script-src 'self'` blocks inline scripts. It limits the damage of an XSS bug but does not replace escaping.
