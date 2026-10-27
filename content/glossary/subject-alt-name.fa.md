+++
title = "SubjectAltName (SAN)"
summary = "SAN: افزونه‌ای که نام‌ها و IPهای معتبر برای گواهی را فهرست می‌کند."
category = "Networking"
fa_title = "SubjectAltName (SAN)"
related = ["x509-certificate", "tls"]
posts = ["net-tls-openssl"]
+++

کلاینت‌های امروزی نام میزبان را فقط با فهرست SAN (نام DNS و آدرس IP) تطبیق می‌دهند. فیلد Common Name تنها کافی نیست؛ مثلاً Go چنین گواهی‌ای را رد می‌کند.
