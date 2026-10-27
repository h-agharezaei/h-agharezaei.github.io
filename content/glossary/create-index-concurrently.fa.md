+++
title = "CREATE INDEX CONCURRENTLY"
summary = "ساخت ایندکس بدون بلوکه کردن نوشتن، به قیمت چند گذر بیشتر و احتمال یک ایندکس INVALID در صورت شکست."
category = "Databases"
fa_title = "CREATE INDEX CONCURRENTLY"
related = ["lock", "migration"]
posts = ["db-zero-downtime-migrations"]
+++

داخل بلوک تراکنش اجرا نمی‌شود. اگر شکست بخورد، ایندکس نیمه‌کاره با `indisvalid = false` می‌ماند و باید حذف شود.
