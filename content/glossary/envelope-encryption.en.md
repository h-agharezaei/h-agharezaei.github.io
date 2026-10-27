+++
title = "Envelope encryption"
summary = "Encrypting data with a random per-record key that is itself encrypted by a master key."
category = "Security"
related = ["aes-gcm", "key-rotation"]
posts = ["sec-secrets-management"]
+++

Each record gets its own data key (DEK), stored wrapped by a key-encryption key (KEK) together with the KEK id. Rotating the KEK only rewraps the small DEKs, not the data.
