+++
title = "Output encoding"
summary = "escape کردن داده برای همان زمینه‌ای که در آن نوشته می‌شود (بدنه‌ی HTML، attribute، JavaScript، URL)."
category = "Security"
fa_title = "Output encoding"
related = ["xss"]
posts = ["sec-injection-xss"]
+++

هر زمینه کاراکترهای خطرناک خودش را دارد، پس یک تابع escape کافی نیست. `html/template` در Go بر اساس جای قرارگیری در قالب، تابع درست را خودکار انتخاب می‌کند.
