+++
title = "Swap"
summary = "Disk (or compressed memory) space the kernel uses to move rarely used anonymous memory pages out of RAM."
category = 'Linux'
related = ["page-cache", "oom-killer"]
posts = ["linux-memory-page-cache-oom"]
+++

`SwapTotal` and `SwapFree` in `/proc/meminfo` show its size and use. Swap can postpone an out-of-memory situation, but a machine that constantly swaps is usually slow.
