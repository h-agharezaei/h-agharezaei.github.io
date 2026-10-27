+++
title = "Shannon entropy"
summary = "A measure of how random a string looks, in bits per character."
category = "Security"
related = ["secret-scanning"]
posts = ["sec-secrets-management"]
+++

Random keys use many different characters evenly, so their entropy is high; ordinary words score lower. Scanners use it to flag key-like strings, at the cost of false positives such as checksums.
