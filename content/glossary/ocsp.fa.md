+++
title = "OCSP"
summary = "راهی برای پرسیدن از CA که آیا یک گواهی مشخص ابطال شده است."
category = "Security"
fa_title = "OCSP"
related = ["certificate-authority", "x509-certificate"]
posts = ["sec-tls-x509-certificates"]
+++

به‌جای دانلود کل فهرست ابطال، کلاینت (یا خود سرور با stapling) درباره‌ی یک شماره‌ی سریال از CA می‌پرسد. این را اجرا نکردم؛ تا جایی که می‌دانم کلاینت استاندارد TLS در Go به‌تنهایی ابطال را بررسی نمی‌کند.
