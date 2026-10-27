+++
title = "ptrace"
fa_title = "ptrace"
summary = "فراخوانی که اجازه می‌دهد یک پروسه پروسه‌ی دیگر را ببیند و کنترل کند؛ strace و دیباگرها از آن استفاده می‌کنند."
category = "Linux"
related = ["strace", "linux-capabilities", "syscall"]
posts = ["linux-strace-perf"]
+++

**ptrace** فراخوان Linux است که یک tracer با آن پروسه‌ی tracee را متوقف می‌کند، رجیسترها و حافظه‌اش را می‌خواند و ادامه می‌دهد. طبق man page برای وصل شدن مجوز لازم است، مثلاً CAP_SYS_PTRACE برای پروسه‌های کاربران دیگر.
