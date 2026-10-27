+++
title = "Path compression"
fa_title = "فشرده‌سازی مسیر"
summary = "در Find هر گره‌ی روی مسیر را مستقیم به ریشه وصل کن تا Findهای بعدی کوتاه‌تر شوند."
category = "Algorithms"
related = ["union-find", "union-by-size"]
posts = ["algo-tries-union-find"]
+++

وقتی `Find(x)` ریشه را پیدا کرد، path compression والد هر گرهٔ مسیر را برابر همان ریشه می‌کند. هزینه یک بار پرداخت می‌شود و Findهای بعدی روی همان گره‌ها یک گام می‌شوند.
