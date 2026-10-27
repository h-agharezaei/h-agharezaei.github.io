+++
title = "Free-threaded Python"
summary = "ساختی از CPython که از 3.13 به‌صورت گزینه در دسترس است و بدون GIL اجرا می‌شود."
category = "Python"
fa_title = "Python بدون GIL (free-threaded)"
related = ["gil", "thread"]
posts = ["py-gil-threading"]
+++

در ساخت free-threaded (`python3.14t`) thread‌های Python می‌توانند هم‌زمان روی چند هسته اجرا شوند. کدی که به GIL تکیه می‌کرد تا race را پنهان کند، مثل `counter += 1`، ممکن است update از دست بدهد. [GIL](/fa/glossary/gil/) را ببینید.
