+++
title = "Event loop"
summary = "حلقه‌ای که به JavaScript تک‌threaded اجازه می‌دهد با اجرای callback در لحظه‌ی آماده شدن، چند عملیات منتظر را مدیریت کند."
category = "Node.js"
fa_title = "ایونت‌لوپ"
related = ["libuv", "microtask", "thread-pool"]
posts = ["node-event-loop"]
+++

event loop مدام از فازها (timers، poll، check، close) می‌گذرد و callbackهای آماده را اجرا می‌کند. JavaScript شما روی یک thread اجرا می‌شود، پس یک کار همگام طولانی همه‌چیز را عقب می‌اندازد.
