+++
title = "SSH certificate"
summary = "A public key signed by a CA key, with principals and a validity period, instead of a list of raw keys."
category = "Linux"
related = ["ssh-key-pair", "certificate-authority", "x509-certificate"]
posts = ["linux-ssh-keys"]
+++

Made with ssh-keygen -s and read with ssh-keygen -L. Servers trust the CA via TrustedUserCAKeys. Unlike [x509](/glossary/x509-certificate/) there is no chain.
