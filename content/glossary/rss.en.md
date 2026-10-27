+++
title = 'RSS'
summary = "Resident set size: the part of a process's memory currently held in physical RAM, not its whole virtual size."
category = 'Linux'
related = ["process", "memory-leak"]
posts = ["linux-proc-observability", "linux-memory-page-cache-oom"]
+++

**RSS** is the part of a process that is really in RAM. It differs from the virtual size (VSZ) and is usually the more useful number when looking at memory use.
