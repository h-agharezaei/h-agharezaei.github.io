+++
title = "Borrow index"
summary = "یک عدد سراسری رو به رشد که بدهی scaled ذخیره‌شده‌ی هر وام‌گیرنده را به بدهی فعلی تبدیل می‌کند تا بهره با O(1) حساب شود."
category = "Blockchain"
fa_title = "borrow index"
related = ["liquidation", "health-factor"]
posts = ["bc-lending-liquidation"]
+++

هر وام مقدار / index را ذخیره می‌کند و بدهی فعلی حاصل‌ضرب آن در آخرین index است. حساب کردن بهره فقط index را به‌روز می‌کند، نه تک‌تک وام‌گیرنده‌ها. سهم در استخر یا خزانه هم همین ایده را دارد.
