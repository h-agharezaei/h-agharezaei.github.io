+++
title = "Domain event"
fa_title = "رویداد دامنه"
summary = "واقعیتی که در دامنه رخ داده، با فعل گذشته نام‌گذاری می‌شود، مثل OrderPlaced."
category = "Engineering"
related = ["aggregate", "outbox-pattern"]
posts = ["eng-ddd-basics"]
+++

aggregate هنگام تغییر رویدادها را جمع می‌کند و application service فقط بعد از موفقیت ذخیره آن‌ها را منتشر می‌کند (برای انجام مطمئن آن به الگوی [outbox](/fa/glossary/outbox-pattern/) نگاه کنید).
