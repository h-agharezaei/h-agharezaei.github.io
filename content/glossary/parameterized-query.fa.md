+++
title = "Parameterized query"
summary = "دستور SQL با جای‌نگهدار (`$1`) که مقدارها جدا از متن SQL فرستاده می‌شوند."
category = "Security"
fa_title = "Parameterized query"
related = ["sql-injection"]
posts = ["sec-injection-xss"]
+++

دیتابیس اول دستور را parse می‌کند و مقدارها را بعداً جا می‌دهد، پس مقدار هرگز ساختار query را عوض نمی‌کند. نام جدول و ستون نمی‌تواند پارامتر باشد.
