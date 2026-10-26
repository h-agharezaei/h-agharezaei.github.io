+++
title = "Microtask"
summary = "کار کوچکی (callback ی promise یا queueMicrotask) که درست بعد از کد جاری و پیش از ادامه‌ی event loop اجرا می‌شود."
category = "Node.js"
fa_title = "میکروتسک"
related = ["event-loop"]
posts = ["node-event-loop", "node-promises-async-await"]
+++

صف microtask بعد از هر callback کامل خالی می‌شود. زنجیره‌ای از microtaskها که مدام microtask تازه اضافه می‌کند می‌تواند timer و I/O را گرسنه نگه دارد.
