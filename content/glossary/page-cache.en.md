+++
title = "Page cache"
summary = "The kernel's in-memory cache of file contents, which makes repeated reads of a file avoid the disk and is reclaimed when memory is needed."
category = 'Linux'
related = ["rss", "overcommit"]
posts = ["linux-memory-page-cache-oom"]
+++

According to proc_meminfo(5), `Cached` is the in-memory cache for files read from disk (the page cache). Because it can be reclaimed, it counts toward `MemAvailable`, so a large `buff/cache` is normal, not a leak.
