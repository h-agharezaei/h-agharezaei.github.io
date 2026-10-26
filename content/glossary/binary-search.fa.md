+++
title = "Binary search"
summary = "جست‌وجویی که در هر قدم نیمی از بازه را کنار می‌گذارد، در زمان O(log n)."
category = "Algorithms"
fa_title = "جست‌وجوی دودویی"
related = ["git-bisect"]
posts = ["git-bisect", "algo-big-o-measured", "db-indexes-btree-explain"]
+++

عنصر وسط را نگاه کنید، تصمیم بگیرید جواب در کدام نیمه می‌تواند باشد و تکرار کنید. ۱۰۰۰ آیتم حداکثر حدود ۱۰ قدم لازم دارد. [git bisect](/fa/glossary/git-bisect/) همین را روی تاریخچه‌ی commitها اجرا می‌کند.
