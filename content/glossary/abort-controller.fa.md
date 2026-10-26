+++
title = "AbortController"
summary = "شیء استانداردی که از طریق AbortSignal لغو شدن را به عملیات async خبر می‌دهد."
category = "Node.js"
fa_title = "AbortController"
related = ["promise"]
posts = ["node-promises-async-await"]
+++

`controller.signal` را به APIای که پشتیبانی می‌کند می‌دهید (timer، `fetch`، `fs` و...). صدا زدن `controller.abort()` باعث می‌شود عملیات با `AbortError` reject شود. `AbortSignal.timeout(ms)` سیگنالی می‌سازد که خودش بعد از مدتی abort می‌شود.
