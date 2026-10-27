+++
title = "Overcommit"
summary = "Letting processes reserve more virtual memory than physical RAM plus swap, because most of it is never touched."
category = 'Linux'
related = ["oom-killer", "swap"]
posts = ["linux-memory-page-cache-oom"]
+++

According to the kernel docs, `vm.overcommit_memory` is 0 (heuristic, default), 1 (always allow) or 2 (never overcommit). With overcommit, a failure shows up later as an OOM kill rather than as a failed `malloc`.
