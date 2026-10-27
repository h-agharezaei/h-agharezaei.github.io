+++
title = "Command injection"
summary = "باگی که در آن ورودی کاربر بخشی از خط فرمان shell می‌شود و آنچه اجرا می‌شود را عوض می‌کند."
category = "Security"
fa_title = "Command injection"
related = ["sql-injection", "rce"]
posts = ["sec-injection-xss"]
+++

وقتی پیش می‌آید که برنامه یک رشته بسازد و به `sh -c` بدهد. راه‌حل اجرای مستقیم برنامه با لیست آرگومان و بدون shell است تا ورودی فقط یک آرگومان بماند.
