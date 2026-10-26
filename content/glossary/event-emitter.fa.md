+++
title = "EventEmitter"
summary = "شیء publish/subscribe داخلی Node: event با نام emit می‌شود و listenerها واکنش نشان می‌دهند."
category = "Node.js"
fa_title = "EventEmitter"
related = ["unhandled-rejection"]
posts = ["node-errors-unhandled-rejections"]
+++

بیشتر اشیای I/O در Node.js (سرور، stream) EventEmitter هستند. event با نام ویژه‌ی `error` فرق دارد: اگر listener نداشته باشد، خطا throw می‌شود و می‌تواند process را از کار بیندازد.
