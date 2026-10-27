+++
title = "Password hashing"
summary = "تابع یک‌طرفه‌ی عمداً کند و دارای salt برای ذخیره‌ی پسورد، تا نشت پایگاه داده پسوردها را فاش نکند."
category = "Security"
fa_title = "هش کردن پسورد"
related = ["salt", "bcrypt", "argon2"]
posts = ["sec-password-hashing"]
+++

برخلاف هش سریعی مثل SHA-256، هش پسورد طوری تنظیم می‌شود که هر حدس زمان (و حافظه) واقعی هزینه داشته باشد. از bcrypt یا argon2id استفاده کنید، نه هش سریع ساده.
