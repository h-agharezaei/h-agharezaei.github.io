+++
title = "Length extension attack"
summary = "An attack on hashes like SHA-256 where knowing H(secret||msg) lets you compute H(secret||msg||extra) without the secret."
category = "Security"
related = ["hmac"]
posts = ["sec-crypto-mistakes"]
+++

It follows from how Merkle-Damgard hashes keep their internal state. HMAC is the standard fix.
