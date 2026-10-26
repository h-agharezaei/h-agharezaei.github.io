+++
title = "Operational error"
summary = "شکست مورد انتظار در زمان اجرا (ورودی بد، رکورد ناموجود، timeout)، در مقابل باگ."
category = "Node.js"
fa_title = "خطای عملیاتی (operational)"
related = ["unhandled-rejection"]
posts = ["node-errors-unhandled-rejections"]
+++

خطاهای عملیاتی handle می‌شوند و به یک پاسخ نگاشت می‌شوند. خطای برنامه‌نویس (مثلاً `TypeError` ناشی از باگ) یعنی وضعیت process مشکوک است و واکنش امن، لاگ و restart است.
