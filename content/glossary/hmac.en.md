+++
title = "HMAC"
summary = "A message authentication code built from a hash and a secret key; unlike sha256(secret||msg) it resists length extension."
category = "Security"
related = ["length-extension-attack", "constant-time-comparison"]
posts = ["sec-crypto-mistakes", "sec-logging-audit-incident-response"]
+++

In Go: `hmac.New(sha256.New, key)`, write the message, `Sum(nil)`. Compare tags with `hmac.Equal`.
