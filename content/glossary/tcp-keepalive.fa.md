+++
title = "TCP keepalive"
summary = "بسته‌های پروبی که کرنل روی اتصال بیکار می‌فرستد تا مرگ طرف مقابل را تشخیص دهد."
category = "Networking"
fa_title = "keepalive در TCP"
related = ["tcp", "socket"]
posts = ["net-tcp-handshake-states"]
+++

وقتی `SO_KEEPALIVE` روشن باشد، کرنل پس از مدتی بیکاری روی اتصال پروب‌های کوچک می‌فرستد. اگر طرف مقابل هیچ‌وقت جواب ندهد اتصال با خطا بسته می‌شود. این با keep-alive در HTTP که درباره‌ی استفاده‌ی دوباره از اتصال است فرق دارد.
