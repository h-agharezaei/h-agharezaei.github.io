+++
title = "known_hosts"
summary = "The client-side file of server host keys already trusted, used to detect a changed or fake server."
category = "Linux"
related = ["ssh-key-pair", "authorized-keys"]
posts = ["linux-ssh-keys"]
+++

The first connection is trust on first use: you accept the fingerprint and it is stored. If it later differs, ssh warns that the host identification has changed. Host names can be hashed with ssh-keygen -H.
