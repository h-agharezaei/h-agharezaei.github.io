+++
title = "Head-of-line blocking"
summary = "یک مورد کند در ابتدای صف، همه‌ی موارد پشت سرش را معطل می‌کند."
category = "Networking"
fa_title = "انسداد سر صف (head-of-line blocking)"
related = ["multiplexing", "tcp"]
posts = ["net-http2"]
+++

در HTTP/1.1 هر اتصال هر بار یک پاسخ را جواب می‌دهد، پس پاسخ کند، بعدی‌ها را معطل می‌کند. HTTP/2 این را در سطح HTTP حل می‌کند، اما TCP بایت‌ها را به ترتیب تحویل می‌دهد و یک بسته‌ی گم‌شده می‌تواند همه‌ی stream‌های آن اتصال را متوقف کند.
