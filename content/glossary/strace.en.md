+++
title = "strace"
summary = "Linux tool that prints the system calls and signals of a process."
category = "Linux"
related = ["syscall", "ptrace", "errno"]
posts = ["linux-strace-perf"]
+++

**strace** runs a command, or attaches to a running process, and prints each system call with its arguments and return value. It relies on [ptrace](/glossary/ptrace/), so a traced process runs slower.
