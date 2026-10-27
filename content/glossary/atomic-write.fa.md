+++
title = "Atomic write"
summary = "نوشتن فایل به شکلی که خواننده یا محتوای قدیمی را می‌بیند یا جدید را، هرگز نیمه‌نوشته را."
category = "Linux"
fa_title = "نوشتن اتمی"
related = ["file-permissions", "race-condition"]
posts = ["linux-scripting-cron-safely"]
+++

روش معمول این است که در همان پوشه فایل موقت بنویسیم و بعد آن را روی مقصد rename کنیم. در سیستم‌فایل‌های POSIX، rename داخل یک سیستم‌فایل نام را در یک گام جایگزین می‌کند.
