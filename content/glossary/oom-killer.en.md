+++
title = 'OOM killer'
summary = 'The kernel mechanism that kills a process when memory runs out, system-wide or inside a cgroup that hit memory.max.'
category = 'Linux'
related = ["cgroup", "container"]
posts = ["linux-cgroups-namespaces"]
+++

According to the cgroup v2 docs, when usage reaches `memory.max` and cannot be reduced, the OOM killer is invoked in that cgroup, and `memory.events` counts it in `oom_kill`.
