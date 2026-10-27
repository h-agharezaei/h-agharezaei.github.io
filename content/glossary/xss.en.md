+++
title = "XSS"
summary = "Cross-site scripting: attacker-controlled text is rendered as HTML or JavaScript in another user's browser."
category = "Security"
related = ["output-encoding", "content-security-policy", "httponly"]
posts = ["sec-injection-xss"]
+++

It happens when untrusted input is written into a page without escaping for the place it lands in. The main defense is context-aware output encoding, with a Content Security Policy as a second layer.
