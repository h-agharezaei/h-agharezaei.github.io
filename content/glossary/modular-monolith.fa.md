+++
title = "Modular monolith"
fa_title = "modular monolith (مونولیت ماژولار)"
summary = "یک واحد استقرار که ماژول‌هایش فقط با interfaceهای باریک حرف می‌زنند."
category = "Distributed"
related = ["microservices", "distributed-monolith"]
posts = ["ds-modular-monolith-vs-microservices"]
+++

یک modular monolith مثل یک برنامه‌ی واحد استقرار می‌شود، ولی به ماژول‌هایی با مرز روشن تقسیم شده است. هر ماژول یک interface کوچک نشان می‌دهد و بقیه را پنهان می‌کند؛ ماژول‌های دیگر فقط از همان interface استفاده می‌کنند. یک process و یک transaction دارید و امکان جداکردن بعدی یک ماژول هم می‌ماند.
