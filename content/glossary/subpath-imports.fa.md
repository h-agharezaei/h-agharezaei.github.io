+++
title = "Subpath imports"
summary = "فیلد `imports` در package.json: نام‌های مستعار خصوصی که با `#` شروع می‌شوند و به فایل نگاشت می‌شوند."
category = "Node.js"
fa_title = "subpath imports"
related = ["esm"]
posts = ["node-project-structure-config"]
+++

فیلد `imports` در package.json: نام‌های مستعار خصوصی که با `#` شروع می‌شوند و به فایل نگاشت می‌شوند. `import x from '#config'` از طریق package.json حل می‌شود و دیگر مسیرهای `../../` طولانی لازم نیست. این نام‌ها فقط داخل همان پکیج کار می‌کنند.
