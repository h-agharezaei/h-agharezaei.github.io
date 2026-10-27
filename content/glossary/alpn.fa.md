+++
title = "ALPN"
summary = "ALPN: مذاکره‌ی پروتکل برنامه (مثل h2 یا http/1.1) داخل TLS."
category = "Networking"
fa_title = "ALPN"
related = ["tls", "sni"]
posts = ["net-tls-openssl", "net-http2"]
+++

در handshake کلاینت فهرستی از پروتکل‌ها (`h2` و `http/1.1`) می‌فرستد و سرور یکی را انتخاب می‌کند. HTTPS همین‌طور بدون رفت‌وبرگشت اضافه بین HTTP/2 و HTTP/1.1 تصمیم می‌گیرد.
