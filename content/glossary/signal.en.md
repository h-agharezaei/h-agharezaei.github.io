+++
title = 'Signal'
summary = 'A small asynchronous message the kernel or another process sends to a process, such as SIGTERM or SIGINT.'
category = 'Linux'
related = ["sigterm", "sigkill", "process"]
posts = ["linux-processes-signals"]
+++

A small asynchronous message the kernel or another process sends to a process, such as SIGTERM or SIGINT. A process may catch most signals with a handler (`trap` in shell), ignore them, or take the default action. SIGKILL and SIGSTOP cannot be caught.
