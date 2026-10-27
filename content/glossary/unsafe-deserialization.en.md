+++
title = "Unsafe deserialization"
summary = "Rebuilding objects from untrusted bytes with a format that can run code while decoding, such as Python pickle."
category = "Security"
related = ["pickle", "ssrf"]
posts = ["sec-ssrf-deserialization"]
+++

Some formats describe not only data but also which function to call to rebuild it. If an attacker controls the bytes, they choose the function. Plain-data formats like JSON, plus schema validation, avoid this. See [pickle](/glossary/pickle/).
