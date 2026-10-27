+++
title = "Union by size"
fa_title = "ادغام بر اساس اندازه"
summary = "هنگام ادغام دو درخت، کوچک‌تر را زیر ریشه‌ی بزرگ‌تر بگذار تا درخت‌ها کم‌عمق بمانند."
category = "Algorithms"
related = ["union-find", "path-compression"]
posts = ["algo-tries-union-find"]
+++

union by size برای هر ریشه اندازه نگه می‌دارد و همیشه درخت کوچک‌تر را زیر بزرگ‌تر می‌آویزد. عمق یک گره فقط وقتی زیاد می‌شود که درخت‌اش دست‌کم دو برابر شود، پس عمق حداکثر log2 n می‌ماند. union by rank همین ایده با تخمینی از ارتفاع است.
