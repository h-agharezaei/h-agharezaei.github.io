+++
title = "Consistent hashing"
summary = "نگاشت کلید به node که با حذف یک node فقط کلیدهای همان جابه‌جا می‌شوند."
category = "Networking"
fa_title = "consistent hashing"
related = ["load-balancer", "hash-table"]
posts = ["net-load-balancer-l4-l7", "algo-bloom-filter-consistent-hashing", "ds-sharding-consistent-hashing"]
+++

nodeها (معمولاً با چند نقطه برای هرکدام) روی یک حلقه‌ی hash قرار می‌گیرند و هر کلید به نقطه‌ی بعدی در جهت ساعت می‌رود. برخلاف `hash % N`، با حذف یک node فقط کلیدهای همان node دوباره نگاشت می‌شوند.
