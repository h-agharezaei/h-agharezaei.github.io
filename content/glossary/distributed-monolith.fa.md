+++
title = "Distributed monolith"
fa_title = "distributed monolith (مونولیت توزیع‌شده)"
summary = "سرویس‌هایی که از راه شبکه جدا شده‌اند ولی هنوز باید با هم تغییر کنند، مستقر شوند و خراب شوند."
category = "Distributed"
related = ["microservices", "modular-monolith"]
posts = ["ds-modular-monolith-vs-microservices"]
+++

distributed monolith هزینه‌های microservice را دارد بدون سودهایش. نشانه‌های رایج: استقرار قفل‌شده با هم، دیتابیس مشترک، و فراخوانی‌های پرحرف که یک درخواست را به چندین فراخوانی باز می‌کنند. معمولاً یعنی مرزها پیش از فهمیده‌شدن کشیده شده‌اند.
