+++
title = "Output encoding"
summary = "Escaping data for the exact context (HTML body, attribute, JavaScript, URL) it is written into."
category = "Security"
related = ["xss"]
posts = ["sec-injection-xss"]
+++

Each context has different dangerous characters, so one escape function is not enough. Go's `html/template` picks the right one automatically from the template position.
