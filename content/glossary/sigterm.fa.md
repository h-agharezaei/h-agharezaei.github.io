+++
title = "SIGTERM"
summary = "سیگنال مؤدبانه‌ای که از پروسه می‌خواهد متوقف شود و پروسه می‌تواند قبلش آن را بگیرد و تمیزکاری کند."
category = "Node.js"
fa_title = "SIGTERM"
related = ["graceful-shutdown"]
posts = ["node-profiling-memory-shutdown", "linux-processes-signals"]
+++

orchestratorها آن را قبل از SIGKILL (که نمی‌شود گرفتش) می‌فرستند. در Node.js با `process.once('SIGTERM', ...)` مدیریتش می‌کنید.
