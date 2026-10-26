+++
title = "Promise"
summary = "مقداری که نماینده‌ی نتیجه‌ای است که هنوز آماده نیست: اول pending، بعد fulfilled یا rejected."
category = "Node.js"
fa_title = "پرامیس"
related = ["async-await", "microtask"]
posts = ["node-promises-async-await"]
+++

یک promise فقط یک بار به یک مقدار یا یک خطا تبدیل می‌شود. کار بعدی را با `.then` و `.catch` به آن وصل می‌کنید یا با [async/await](/fa/glossary/async-await/) منتظرش می‌مانید؛ callbackها به شکل [microtask](/fa/glossary/microtask/) اجرا می‌شوند.
