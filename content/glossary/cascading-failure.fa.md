+++
title = "Cascading failure"
fa_title = "cascading failure (خرابی زنجیره‌ای)"
summary = "خرابی‌ای که پخش می‌شود: یک جزء کند یا خراب callerهایش را فرسوده می‌کند و آن‌ها callerهای خودشان را."
category = "Distributed"
related = ["circuit-breaker", "bulkhead", "partial-failure"]
posts = ["ds-circuit-breaker-bulkhead"]
+++

زنجیره‌ی معمول: وابستگی کند می‌شود، درخواست‌ها منتظرش جمع می‌شوند، thread یا حافظه تمام می‌شود و سرویس برای همه کند می‌شود. timeout، circuit breaker، bulkhead و load shedding ترمزهای استاندارد هستند.
