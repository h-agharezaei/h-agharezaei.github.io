+++
title = "Dead tuple"
summary = "نسخه‌ای از ردیف که هیچ تراکنش فعلی یا آینده‌ای دیگر نمی‌بیند، اما تا وقتی VACUUM پاکش نکرده جا اشغال می‌کند."
category = "Databases"
fa_title = "dead tuple"
related = ["mvcc", "vacuum", "table-bloat"]
posts = ["db-mvcc-vacuum"]
+++

update و delete نسخه‌ی مرده تولید می‌کنند. تا وقتی یک تراکنش قدیمی هنوز بتواند نسخه‌ای را ببیند، آن نسخه «مرده ولی هنوز قابل حذف نیست».
