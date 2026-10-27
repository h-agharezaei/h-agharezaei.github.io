+++
title = "ECB mode"
summary = "A block cipher mode that encrypts every block independently, so equal plaintext blocks give equal ciphertext blocks."
category = "Security"
related = ["aead"]
posts = ["sec-crypto-mistakes"]
+++

ECB (electronic codebook) leaks the structure of the data: 64 bytes of `A` gave four identical blocks. Do not use it; use an AEAD mode.
