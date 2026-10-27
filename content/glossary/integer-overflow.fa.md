+++
title = "Integer overflow"
fa_title = "سرریز عدد صحیح"
summary = "نتیجه‌ای که در نوع عدد صحیح جا نمی‌شود؛ در Go بی‌صدا دور می‌زند."
category = "Algorithms"
related = ["binary-search"]
posts = ["algo-binary-search-invariants", "sec-fuzzing", "sec-memory-safety-c-vs-rust"]
+++

وقتی نتیجه‌ی محاسبه در نوع عدد صحیح جا نمی‌شود. در Go عددهای علامت‌دار بی‌صدا دور می‌زنند، پس جمع دو عدد مثبت بزرگ می‌تواند منفی شود.
