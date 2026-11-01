+++
title = "Storage collision"
summary = "دو تکه کد که از یک slot برای متغیرهای متفاوت استفاده می‌کنند، پس هر کدام داده‌ی دیگری را می‌خواند."
category = "Blockchain"
fa_title = "تداخل storage (storage collision)"
related = ["proxy-pattern", "delegatecall", "storage-layout"]
posts = ["bc-gas-optimization-proxies"]
+++

علت رایج: نسخه‌ی جدید implementation متغیرهای state را جابه‌جا، حذف یا عوض می‌کند. فقط به آخر اضافه کنید و قبل از ارتقا چیدمان storage را مقایسه کنید.
