+++
title = "Overcommit"
fa_title = "overcommit"
summary = "اجازه دادن به پروسه‌ها که بیش از مجموع RAM و swap حافظه‌ی مجازی رزرو کنند، چون بیشترش هیچ‌وقت استفاده نمی‌شود."
category = 'Linux'
related = ["oom-killer", "swap"]
posts = ["linux-memory-page-cache-oom"]
+++

طبق مستندات کرنل `vm.overcommit_memory` برابر ۰ (روش تخمینی، پیش‌فرض)، ۱ (همیشه اجازه بده) یا ۲ (هرگز overcommit نکن) است. با overcommit شکست دیرتر و به شکل OOM kill ظاهر می‌شود، نه خطای `malloc`.
