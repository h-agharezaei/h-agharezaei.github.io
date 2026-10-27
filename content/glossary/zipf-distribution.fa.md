+++
title = "Zipf distribution"
fa_title = "توزیع Zipf"
summary = "الگوی دسترسی نامتقارن که در آن چند کلید بیشتر درخواست‌ها را می‌گیرند و دنباله‌ی بلندی کم."
category = "Distributed"
related = ["lru-cache", "hot-key"]
posts = ["ds-capacity-estimation"]
+++

کلید رتبه‌ی r با احتمالی متناسب با 1/r^s درخواست می‌شود. ترافیک واقعی اغلب چنین چولگی‌ای دارد و برای همین cache کوچک می‌تواند hit rate بالایی داشته باشد.
