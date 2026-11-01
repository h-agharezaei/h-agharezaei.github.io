+++
title = "State machine"
summary = "مدلی که در آن یک موجودیت همیشه در یکی از چند حالت مشخص است و فقط از مسیرهای مجاز صریح به حالت دیگر می‌رود."
category = "Engineering"
fa_title = "ماشین حالت (state machine)"
related = ["idempotency"]
posts = ["bc-exchange-deposits-withdrawals"]
+++

نوشتن مسیرهای مجاز (مثلاً `pending -> credited` ولی هرگز `credited -> pending`) خیلی از باگ‌ها را به خطای آشکار تبدیل می‌کند. در دیتابیس هر به‌روزرسانی را با حالت فعلی مورد انتظار محافظت کنید: `UPDATE ... SET status = 'credited' WHERE status = 'pending'`.
