+++
title = "RST"
summary = "یک segment در TCP که اتصال را فوراً و بدون تبادل مرتب FIN قطع می‌کند."
category = "Networking"
fa_title = "RST"
related = ["tcp", "half-close"]
posts = ["net-tcp-handshake-states"]
+++

FIN یعنی «من فرستادن را تمام کردم» و به‌ترتیب تحویل می‌شود؛ RST یعنی «این اتصال مرده است». طرف مقابل خطای `ECONNRESET` می‌گیرد و connect به port بسته روی loopback هم با RST جواب داده می‌شود (`connection refused`).
