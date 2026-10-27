+++
title = "Rate limiting"
summary = "سقف‌گذاری روی تعداد درخواست‌های یک کلاینت در بازه‌ی زمانی."
category = "Distributed"
fa_title = "محدودسازی نرخ"
related = ["token-bucket", "sliding-window", "load-shedding"]
posts = []
+++

محدودسازی نرخ سرویس را از بار زیاد و از یک کلاینت پرسروصدا حفظ می‌کند. برای هر کلید، مثل کلاینت یا tenant، جواب می‌دهد پذیرش یا رد (اغلب HTTP 429).
