+++
title = "Pydantic"
summary = "کتابخانه‌ای در Python که داده را با type hint اعتبارسنجی و تبدیل می‌کند."
category = "Python"
fa_title = "Pydantic"
related = ["type-hint", "schema-validation"]
posts = ["py-fastapi-pydantic"]
+++

Pydantic از کلاس‌های دارای annotation مدل می‌سازد. `Model.model_validate(data)` داده را بررسی و تبدیل می‌کند (حالت lax رشته‌ی `"5"` را به 5 تبدیل می‌کند) و در صورت خطا `ValidationError` با فهرست خطاها می‌دهد. FastAPI آن را برای body ‌ی درخواست و پاسخ استفاده می‌کند.
