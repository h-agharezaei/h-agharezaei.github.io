+++
title = "Schema validation"
summary = "بررسی داده‌ی غیرقابل‌اعتماد با یک شکل تعریف‌شده (نوع، بازه، فیلدهای الزامی) در مرز برنامه، پیش از آنکه بقیه‌ی کد از آن استفاده کند."
category = "Node.js"
fa_title = "اعتبارسنجی با schema"
related = ["json-schema", "trust-boundary", "mass-assignment"]
posts = ["node-validation-zod"]
+++

schema توصیف می‌کند ورودی معتبر چه شکلی است؛ parse یا داده‌ی تمیز برمی‌گرداند یا فهرستی از issueها. کتابخانه‌هایی مثل Zod این کار را به‌جای فایل schema جدا، در خود کد انجام می‌دهند.
