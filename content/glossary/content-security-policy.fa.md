+++
title = "Content Security Policy"
summary = "هدر پاسخی که به مرورگر می‌گوید صفحه از چه منبع‌هایی اجازه‌ی اسکریپت و محتوای دیگر دارد."
category = "Security"
fa_title = "Content Security Policy"
related = ["xss"]
posts = ["sec-injection-xss", "sec-csrf-cors-headers"]
+++

مثلاً `script-src 'self'` اسکریپت inline را می‌بندد. دامنه‌ی خسارت یک باگ XSS را کم می‌کند، ولی جای escape را نمی‌گیرد.
