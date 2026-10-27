+++
title = "HSTS"
summary = "HTTP Strict Transport Security: a header telling the browser to use only HTTPS for this site for a period."
category = "Security"
related = ["content-security-policy"]
posts = ["sec-csrf-cors-headers"]
+++

Per its spec it is ignored when received over plain HTTP, so it only matters on HTTPS responses.
