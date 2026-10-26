+++
title = "Unhandled rejection"
summary = "promise ردشده‌ای که هیچ‌کس با catch یا try/catch رسیدگی‌اش نکرده."
category = "Node.js"
fa_title = "unhandled rejection"
related = ["promise"]
posts = ["node-promises-async-await"]
+++

از Node 15 به بعد رفتار پیش‌فرض این است که process با exit code برابر 1 از کار می‌افتد (اینجا روی Node 20 بررسی شد). همیشه [promise](/fa/glossary/promise/) را handle یا return کنید.
