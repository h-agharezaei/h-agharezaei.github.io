+++
title = "Non-repeatable read"
fa_title = "خواندن ناتکرارپذیر"
summary = "خواندن یک ردیف دو بار در یک تراکنش و گرفتن دو مقدار متفاوت."
category = "Databases"
related = ["isolation-level", "phantom-read"]
posts = ["db-isolation-levels-anomalies"]
+++

وقتی رخ می‌دهد که تراکنش دیگری بین دو خواندن شما تغییری commit کند. PostgreSQL آن را در READ COMMITTED اجازه می‌دهد و در REPEATABLE READ نمی‌دهد.
