+++
title = "Thread pool"
summary = "مجموعه‌ی ثابتی از thread که کارهای بلاک‌کننده (فایل، crypto، DNS) را برای Node.js اجرا می‌کند؛ اندازه‌ی پیش‌فرض ۴."
category = "Node.js"
fa_title = "ترد پول"
related = ["libuv", "event-loop"]
posts = ["node-event-loop", "py-gil-threading", "py-fastapi-pydantic"]
+++

اندازه‌اش با متغیر محیطی `UV_THREADPOOL_SIZE` تنظیم می‌شود. کارهای بیشتر از اندازه‌ی pool در صف می‌مانند و دسته‌دسته تمام می‌شوند.
