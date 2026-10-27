+++
title = "Key rotation"
summary = "Replacing a key with a new one on a schedule or after exposure, while old data stays readable."
category = "Security"
related = ["envelope-encryption"]
posts = ["sec-secrets-management"]
+++

Store a key id with every ciphertext so several keys can coexist. After a leak, rotate first (the old key is compromised), then clean up.
