+++
title = "Lifecycle hook"
summary = "تابعی که فریم‌ورک در مرحله‌ای ثابت از عمر یک درخواست صدا می‌زند، مثلاً پیش از اجرای handler."
category = "Node.js"
fa_title = "hook چرخه‌ی عمر"
related = ["json-schema"]
posts = ["node-fastify-api"]
+++

در Fastify مرحله‌ها با ترتیب ثابت اجرا می‌شوند: `onRequest`، `preValidation`، `preHandler`، handler و بعد `onSend`. hookها جای کارهای مشترک مثل request ID یا هدرها هستند.
