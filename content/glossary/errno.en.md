+++
title = "errno"
summary = "The error code a failed system call reports, such as ENOENT or EACCES."
category = "Linux"
related = ["syscall", "strace"]
posts = ["linux-strace-perf"]
+++

**errno** is the error number a failed system call leaves behind; strace prints its symbol, for example `-1 ENOENT (No such file or directory)`. Reading the symbol usually tells you what to check next.
