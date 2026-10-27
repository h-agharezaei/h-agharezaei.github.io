+++
title = "Read model"
summary = "نسخه‌ای از داده که برای کوئری آماده شده و با اعمال رویدادهای سمت نوشتن ساخته می‌شود؛ ممکن است عقب باشد ولی باید همگرا شود."
category = "Distributed"
fa_title = "مدل خواندن"
related = ["projection","event-sourcing","eventual-consistency"]
posts = ["ds-capstone"]
+++

در CQRS و event sourcing، مدل خواندن یک [projection](/fa/glossary/projection/) از لاگ رویدادهاست. اگر پاک شود با fold کردن دوباره‌ی لاگ ساخته می‌شود؛ پس بعد از رسیدن همه‌ی رویدادها، مدل درست همیشه با fold لاگ برابر است.
