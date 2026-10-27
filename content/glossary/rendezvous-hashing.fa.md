+++
title = "Rendezvous hashing"
fa_title = "Rendezvous hashing"
summary = "هر کلید به node ای می‌رود که بیشترین امتیاز hash(node, key) را دارد (به آن HRW هم می‌گویند)."
category = "Algorithms"
related = ["consistent-hashing"]
posts = ["algo-bloom-filter-consistent-hashing"]
+++

برای هر کلید همه‌ی node ها را با hash ِ جفت امتیاز می‌دهید و بالاترین را برمی‌دارید. حذف یک node فقط کلیدهای خودش را جابه‌جا می‌کند. حلقه لازم نیست ولی هر جست‌وجو O(تعداد node ها) است. مقایسه کنید با [Consistent hashing](/fa/glossary/consistent-hashing/).
