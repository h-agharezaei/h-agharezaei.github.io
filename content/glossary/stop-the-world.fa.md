+++
title = "Stop-the-world"
summary = "مکثی کوتاه که در آن runtime همه‌ی goroutineها را متوقف می‌کند تا کاری را که به دید یکدست نیاز دارد انجام دهد، مثل بخش‌هایی از یک چرخه‌ی GC."
category = "Go"
fa_title = "توقف سراسری"
related = ["goroutine", "garbage-collector"]
posts = ["go-scheduler-gc-internals"]
+++

بیشتر garbage collection در Go هم‌زمان با کد شما اجرا می‌شود، ولی هر چرخه در ابتدا و انتهایش مکث‌های کوتاه stop-the-world دارد (عدد اول و سوم زمان دیواری در یک خط `gctrace`).
