+++
title = "Digital signature"
summary = "A value computed with a private key that anyone with the public key can verify, proving origin and integrity."
category = "Security"
related = ["hmac"]
posts = ["sec-crypto-mistakes"]
+++

Ed25519 signatures are 64 bytes. Changing one byte of the message makes verification fail.
