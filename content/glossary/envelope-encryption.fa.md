+++
title = "Envelope encryption"
summary = "رمز کردن داده با کلید تصادفی هر رکورد که خودش با یک کلید اصلی رمز می‌شود."
category = "Security"
fa_title = "رمزنگاری پاکتی"
related = ["aes-gcm", "key-rotation"]
posts = ["sec-secrets-management"]
+++

هر رکورد کلید داده‌ی خودش (DEK) را دارد که با یک کلید رمزکننده‌ی کلید (KEK) و شناسه‌ی آن ذخیره می‌شود. چرخاندن KEK فقط DEKهای کوچک را دوباره بسته‌بندی می‌کند، نه داده را.
