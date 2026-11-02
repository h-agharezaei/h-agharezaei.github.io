+++
title = "Domain separation"
summary = "افزودن پیشوند یا برچسب به ورودی hash بر اساس کاربرد، تا hashی که برای یک نقش ساخته شده در نقش دیگر قابل استفاده نباشد."
category = "Blockchain"
fa_title = "domain separation"
related = ["second-preimage-attack", "merkle-tree"]
posts = ["bc-merkle-trees-proofs"]
+++

RFC 6962 برگ‌های Merkle را به شکل SHA-256(0x00 || data) و گره‌های داخلی را به شکل SHA-256(0x01 || left || right) hash می‌کند.
