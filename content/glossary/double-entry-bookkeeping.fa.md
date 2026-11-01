+++
title = "Double-entry bookkeeping"
summary = "ثبت هر جابه‌جایی پول به‌صورت چند ردیف روی دست‌کم دو حساب که جمعشان صفر است، تا پولی بی‌صدا ساخته یا گم نشود."
category = "Engineering"
fa_title = "حسابداری دوطرفه (double-entry)"
related = ["idempotency", "audit-log"]
posts = ["bc-exchange-deposits-withdrawals"]
+++

به‌جای به‌روزکردن یک ستون موجودی، هر رویداد یک journal می‌نویسد که ردیف‌هایش هم را خنثی می‌کنند: واریز به حساب کاربر اضافه و از حساب `external` کم می‌کند. موجودی جمع ردیف‌های یک حساب است، تاریخچه بازنویسی نمی‌شود و جمع غیر صفر روی همه‌ی حساب‌ها یعنی باگ.
