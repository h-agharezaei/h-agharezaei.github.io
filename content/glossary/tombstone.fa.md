+++
title = "Tombstone"
fa_title = "tombstone (سنگ‌قبر)"
summary = "نشانه‌ای که هنگام حذف در جدول open addressing باقی می‌ماند تا جست‌وجوها از روی آن عبور کنند."
category = "Algorithms"
related = ["hash-table", "linear-probing"]
posts = ["algo-hash-tables"]
+++

اگر خانه‌ی حذف‌شده صرفاً خالی شود، کلیدی که با probe بعد از آن قرار گرفته بود دست‌نیافتنی می‌شود. tombstone زنجیره را سالم نگه می‌دارد؛ درج بعدی می‌تواند از آن استفاده کند و rehash همه‌شان را دور می‌ریزد.
