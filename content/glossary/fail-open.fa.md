+++
title = "Fail open"
summary = "عبور دادن درخواست‌ها وقتی جزء محافظ، مثل store مربوط به limiter، در دسترس نیست."
category = "Distributed"
fa_title = "fail open"
related = ["rate-limiting", "lease"]
posts = ["ds-case-studies"]
+++

حالت مقابل fail closed است که رد می‌کند. برای هر endpoint جدا انتخاب کنید: برای خواندن‌های ارزان معمولاً دسترس‌پذیری و برای login یا کار گران امنیت.
