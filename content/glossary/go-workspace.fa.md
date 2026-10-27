+++
title = "Go workspace (go.work)"
fa_title = "workspace در Go (go.work)"
summary = "فایل go.work که چند ماژول محلی Go را بدون نسخه‌ی منتشرشده به هم وصل می‌کند."
category = "Engineering"
related = ["monorepo"]
posts = ["eng-monorepo-vs-polyrepo"]
+++

فایل `go.work` با `use` چند پوشه را فهرست می‌کند. تا وقتی فعال است، دستور go ماژول‌های فهرست‌شده را با هم می‌سازد و نسخه‌ی محلی را به نسخه‌ی رجیستری ترجیح می‌دهد. برای توسعه‌ی محلی میان ماژول‌ها است، مثلاً در یک [monorepo](/fa/glossary/monorepo/).
