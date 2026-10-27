+++
title = "authorized_keys"
summary = "The server-side file listing public keys allowed to log in, with optional restrictions per key."
category = "Linux"
related = ["ssh-key-pair"]
posts = ["linux-ssh-keys"]
+++

One key per line, optionally prefixed by options such as restrict, from= and command=. It controls who may log in, not whether the server is genuine (see [known_hosts](/glossary/known-hosts/)).
