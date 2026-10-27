+++
title = "Certificate authority (CA)"
summary = "CA: مرجعی که کلاینت به امضایش روی گواهی‌ها اعتماد می‌کند."
category = "Networking"
fa_title = "مرجع صدور گواهی (CA)"
related = ["x509-certificate", "tls"]
posts = ["net-tls-openssl", "sec-tls-x509-certificates"]
+++

CA امضاکننده‌ی گواهی‌هاست. کلاینت وقتی به یک گواهی اعتماد می‌کند که زنجیره‌ی امضاها به CA‌ای در trust store اش (یا فایل `-CAfile`) برسد. CA خصوصی برای دمو یا شبکه‌ی داخلی همین‌طور کار می‌کند، فقط ماشین‌های شما به آن اعتماد دارند.
