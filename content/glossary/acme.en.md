+++
title = "ACME"
summary = "A protocol that lets software request and renew certificates from a CA automatically."
category = "Security"
related = ["certificate-authority", "x509-certificate"]
posts = ["sec-tls-x509-certificates"]
+++

With ACME the server proves it controls a domain (for example by answering a challenge), and the CA issues a short-lived certificate. Let's Encrypt uses it. Automation is what makes short lifetimes practical.
