+++
title = 'cgroup'
summary = 'A kernel feature that groups processes and limits or accounts for their CPU, memory and process count.'
category = 'Linux'
related = ["namespace", "container", "oom-killer"]
posts = ["linux-cgroups-namespaces"]
+++

A control group (cgroup) is a directory in a tree, usually under `/sys/fs/cgroup` in version 2. You put processes in it by writing their PID to `cgroup.procs`, and files such as `memory.max` and `pids.max` set limits, according to the kernel docs.
