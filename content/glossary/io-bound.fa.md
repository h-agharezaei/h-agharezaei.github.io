+++
title = "I/O-bound"
summary = "کاری که بیشتر زمانش صرف انتظار برای شبکه یا دیسک می‌شود، نه محاسبه."
category = "Engineering"
fa_title = "وابسته به I/O"
related = ["cpu-bound","event-loop"]
posts = ["node-vs-go-when-to-use"]
+++

کار **وابسته به I/O** بیشتر منتظر است، مثلاً منتظر پاسخ یک سرویس بالادستی. [event loop](/fa/glossary/event-loop/) یا تعداد زیادی [goroutine](/fa/glossary/goroutine/) می‌توانند هزاران انتظار را ارزان هم‌پوشانی کنند.
