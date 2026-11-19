+++
title = "managed identity"
summary = "An identity the cloud platform gives to a VM, function or app, so it can get short-lived tokens without any stored password."
category = "Security"
related = ["imds", "oidc", "bearer-token"]
posts = ["agent-framework-pypi-compromise-2026"]
+++

It removes long-lived secrets from config files. The trade-off is that anything that can run code on that resource can ask for its tokens, so the blast radius is the identity's permissions.
