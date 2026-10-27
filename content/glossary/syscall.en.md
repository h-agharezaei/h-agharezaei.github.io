+++
title = 'System call'
summary = 'A request from a program to the kernel, such as open or read; tools like strace list them.'
category = 'Linux'
related = ["process", "file-descriptor"]
posts = ["linux-proc-observability", "linux-strace-perf"]
+++

A **system call** is how a program asks the kernel to do something: open a file, read, create a process. On Linux `strace` lists them for a process.
