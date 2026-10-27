+++
title = 'Namespace'
fa_title = 'namespace'
summary = 'قابلیت کرنل که دید جداگانه‌ای از یک منبع مثل PID، mount، شبکه یا hostname به پروسه می‌دهد.'
category = 'Linux'
related = ["cgroup", "container", "syscall"]
posts = ["linux-cgroups-namespaces", "linux-networking-ip-ss-nftables"]
+++

طبق namespaces(7) چند نوع وجود دارد (mount، PID، network، UTS، IPC، user، cgroup، time). پروسه با `clone(2)` یا `unshare(2)` یا `setns(2)` به آن‌ها می‌پیوندد و لینک‌های `/proc/<pid>/ns/` هویتشان را نشان می‌دهند.
