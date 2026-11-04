+++
title = "black_box"
fa_title = "black_box"
summary = "`std::hint::black_box`: تابعی که مقداری را از دید بهینه‌ساز پنهان می‌کند تا کار benchmark حذف نشود یا موقع کامپایل حل نشود."
category = "Rust"
related = ["criterion"]
posts = ["rust-performance-criterion"]
+++

ورودی را در آن بپیچید (`black_box(n)`) تا کامپایلر آن را ثابت فرض نکند، و از نتیجه استفاده کنید تا دور ریخته نشود. بدون آن، benchmark یک تابع خالص ممکن است کسری از نانوثانیه گزارش کند، چون هیچ کاری اجرا نشده.
