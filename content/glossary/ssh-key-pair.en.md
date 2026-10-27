+++
title = "SSH key pair"
summary = "A private key you keep plus a public key you share, used to log in without a password."
category = "Linux"
related = ["authorized-keys", "known-hosts"]
posts = ["linux-ssh-keys"]
+++

The private file proves who you are by signing a challenge; the public line goes into the server's [authorized_keys](/glossary/authorized-keys/). ed25519 is the compact modern type. The private file must be mode 0600.
