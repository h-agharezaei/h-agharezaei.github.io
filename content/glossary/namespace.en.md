+++
title = 'Namespace'
summary = 'A kernel feature that gives a process its own view of a resource such as PIDs, mounts, network or hostname.'
category = 'Linux'
related = ["cgroup", "container", "syscall"]
posts = ["linux-cgroups-namespaces"]
+++

Per namespaces(7) there are several types (mount, PID, network, UTS, IPC, user, cgroup, time). A process joins them through `clone(2)`, `unshare(2)` or `setns(2)`, and the links in `/proc/<pid>/ns/` identify them.
