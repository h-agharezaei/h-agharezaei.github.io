+++
title = "async/await"
summary = "سینتکسی که کار با promiseها را شبیه کد ترتیبی می‌کند."
category = "Node.js"
fa_title = "async/await"
related = ["promise", "event-loop"]
posts = ["node-promises-async-await"]
+++

تابع `async` همیشه یک [promise](/fa/glossary/promise/) برمی‌گرداند. `await` فقط همان تابع را متوقف می‌کند تا promise تمام شود؛ thread برای [event loop](/fa/glossary/event-loop/) آزاد می‌ماند.
