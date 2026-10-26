+++
title = "Lost update"
fa_title = "به‌روزرسانی گمشده"
summary = "دو تراکنش یک مقدار را می‌خوانند، هر دو نتیجه‌ای محاسبه‌شده از آن را می‌نویسند و یکی بی‌صدا روی دیگری می‌نویسد."
category = "Databases"
related = ["isolation-level", "write-skew"]
posts = ["db-isolation-levels-anomalies"]
+++

علت رایج: read-modify-write در کد اپلیکیشن. راه‌حل: محاسبه را در SQL انجام دهید (`SET balance = balance - 10`)، ردیف را با `SELECT ... FOR UPDATE` قفل کنید یا سطح ایزولاسیون بالاتر و retry به کار ببرید.
