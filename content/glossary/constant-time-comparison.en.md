+++
title = "Constant-time comparison"
summary = "Comparing secrets in a way whose running time does not depend on where they first differ."
category = "Security"
related = ["password-hashing"]
posts = ["sec-password-hashing"]
+++

A normal `==` may stop at the first different byte, which can leak information through timing. In Go use `subtle.ConstantTimeCompare`.
