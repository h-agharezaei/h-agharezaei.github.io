+++
title = "ptrace"
summary = "The system call that lets one process observe and control another; strace and debuggers use it."
category = "Linux"
related = ["strace", "linux-capabilities", "syscall"]
posts = ["linux-strace-perf"]
+++

**ptrace** is the Linux system call a tracer uses to stop a tracee, read its registers and memory, and resume it. According to the man page, attaching needs permission, for example CAP_SYS_PTRACE for other users' processes.
