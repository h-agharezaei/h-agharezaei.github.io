+++
title = "Mutual TLS (mTLS)"
summary = "mTLS: کلاینت هم گواهی می‌دهد و سرور آن را بررسی می‌کند."
category = "Networking"
fa_title = "TLS دوطرفه (mTLS)"
related = ["tls", "certificate-authority"]
posts = ["net-tls-openssl"]
+++

در TLS معمولی فقط سرور هویتش را ثابت می‌کند. در mutual TLS سرور گواهی کلاینت را هم می‌خواهد و اگر نباشد یا CA مورد اعتماد امضایش نکرده باشد اتصال را رد می‌کند. بین سرویس‌های داخلی رایج است.
