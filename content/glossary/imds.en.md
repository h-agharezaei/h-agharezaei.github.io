+++
title = "IMDS"
summary = "Instance Metadata Service: a link-local HTTP endpoint (169.254.169.254) on cloud VMs that tells code about its host and can issue identity tokens."
category = "Security"
related = ["managed-identity", "oidc"]
posts = ["agent-framework-pypi-compromise-2026"]
+++

Code on the machine needs no password to call it, which is convenient and also why malware on the machine can call it too. Whatever the VM's identity may do, the caller can do.
