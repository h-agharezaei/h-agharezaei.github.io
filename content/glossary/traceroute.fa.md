+++
title = "traceroute"
summary = "traceroute لیست روترهای مسیر تا یک میزبان را با فرستادن بسته‌هایی که TTL آن‌ها از ۱ شروع و زیاد می‌شود نشان می‌دهد."
category = "Networking"
fa_title = "تریس‌روت"
related = ["ttl", "icmp"]
posts = ["net-troubleshooting-curl-traceroute"]
+++

ابزاری که بسته‌هایی با TTL (حد گام) رو‌به‌افزایش می‌فرستد. هر روتری که بسته را چون TTL صفر شده دور می‌اندازد، پیام ICMP برمی‌گرداند و همان گام دیده می‌شود. نگاه کنید به [ICMP](/fa/glossary/icmp/).
