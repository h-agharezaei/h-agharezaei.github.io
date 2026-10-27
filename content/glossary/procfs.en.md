+++
title = 'procfs'
summary = "Linux's virtual /proc filesystem, where the kernel exposes process and system state as files."
category = 'Linux'
related = ["process", "file-descriptor"]
posts = ["linux-proc-observability"]
+++

Linux's virtual `/proc` filesystem. Its files are not stored on disk; the kernel generates them when read. For example `/proc/self/status` describes your own process.
