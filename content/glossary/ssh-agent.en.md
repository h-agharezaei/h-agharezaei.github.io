+++
title = "ssh-agent"
summary = "A process that keeps decrypted private keys in memory and signs on behalf of ssh."
category = "Linux"
related = ["ssh-key-pair"]
posts = ["linux-ssh-keys"]
+++

You type the passphrase once; ssh asks the agent over a socket. Anyone who can use that socket can sign as you, which is why agent forwarding to untrusted hosts is risky.
