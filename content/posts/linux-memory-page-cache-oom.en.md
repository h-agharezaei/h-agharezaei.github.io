+++
date = '2027-05-02T10:00:00+03:30'
draft = false
title = 'Memory, the page cache and the OOM killer'
description = 'Linux memory explained from man pages: free vs available, the page cache, overcommit, OOM scores and cgroup limits, plus a Go program that runs on macOS.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "memory", "page-cache", "oom-killer", "go", "macos"]
cover = { image = "/images/covers/linux-memory-page-cache-oom.png", alt = "Memory, the page cache and the OOM killer", hiddenInSingle = true }
+++

I wrote this on a Mac; nothing here ran on Linux. This is the seventh post of the Linux series, after [cgroups and namespaces: the base of containers](/posts/linux-cgroups-namespaces/). The question: why does `free` show little free memory, and why did a service die with exit code 137? Facts come from man pages and kernel docs; Linux-looking text is labelled "illustrative, not captured".

## Reading free and /proc/meminfo

According to proc_meminfo(5), `MemAvailable` is an estimate of memory available for starting new applications without swapping, and `Cached` is the in-memory cache for files read from disk, the {{< term "page-cache" "page cache" >}}. free(1) defines `used` as total minus available, `free` as unused memory (`MemFree`) and `buff/cache` as buffers plus cache.

So a small `free` column is normal: the kernel uses spare RAM for cache and gives it back when needed. Judge `available`. So reading a file twice differs: the first read fills the cache from disk, the second can come from memory. I could not measure it here.

Writes go to the cache first. `Dirty` is memory waiting to be written to disk and `Writeback` is memory being written now. The `vm.dirty_background_ratio` and `vm.dirty_ratio` sysctls set when flushing starts.

## Swap, overcommit and sizes

{{< term "swap" "Swap" >}} moves rarely used pages to disk (`SwapTotal`, `SwapFree`). {{< term "overcommit" "Overcommit" >}} is set by `vm.overcommit_memory`; the docs describe 0 as the default heuristic that rejects obvious overcommits, 1 as always allow, and 2 as never overcommit. `CommitLimit` and `Committed_AS` show the accounting.

Three sizes of a process:

| Name | Meaning | Where |
|---|---|---|
| VSZ | virtual size, mostly never touched | `VmSize` in `/proc/<pid>/status` |
| {{< term "rss" "RSS" >}} | pages resident in RAM | `VmRSS` |
| PSS | RSS with shared pages divided among users | `Pss` in `/proc/<pid>/smaps` |

## Allocated is not resident

I wrote a Go program that allocates four 64 MiB slices, then touches every page, printing runtime counters and the peak RSS from `getrusage`. It ran for real on macOS; bytes only, no timings:

```
start                  HeapAlloc=   0 MiB  HeapSys=   7 MiB  Sys=  11 MiB  maxRSS=   4 MiB
allocated 4 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS=   5 MiB
touched   1 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS=  69 MiB
touched   4 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS= 261 MiB
after drop + GC        HeapAlloc=   0 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS= 261 MiB
```

The heap grew by 256 MiB right away, but RSS stayed near 5 MiB until the pages were written: virtual versus resident, the same idea as VSZ versus RSS. After the {{< term "garbage-collector" "garbage collector" >}} the heap was empty, but `HeapSys` stayed and `maxRSS` is a peak. (`ru_maxrss` is bytes on macOS; I believe kB on Linux.)

## Who gets killed

When memory runs out, the {{< term "oom-killer" "OOM killer" >}} picks a victim. According to the man pages, `/proc/<pid>/oom_score` is the current score, higher meaning more likely, based mainly on memory use. `oom_score_adj` ranges from -1000 to +1000 and is added to the score; -1000 disables OOM killing for that task.

## Containers: killed with free memory on the host

A {{< term "cgroup" "cgroup" >}} has its own limit. The cgroup v2 docs say `memory.max` is the hard limit and the OOM killer is invoked in the cgroup when usage reaches it and cannot be reduced. `memory.high` only throttles and never invokes the killer. `memory.events` counts `oom_kill` among others. That is how a container dies while the host has free RAM; see the previous post.

`/proc/pressure/memory` (PSI) reports `some` and `full` stall shares.

Go's `GOMEMLIMIT` is a soft limit covering the heap and runtime-managed memory, not external memory, per the `runtime` docs. Setting it a bit below the container limit is common practice; see [the Go scheduler and garbage collector](/posts/go-scheduler-gc-internals/).

## Linux tools and what I ran

| Tool | Shows | macOS |
|---|---|---|
| `free` | used, available, cache | not run (`vm_stat`: page size 16384 bytes) |
| `/proc/meminfo` | the fields above | none |
| `vmstat` | swap and paging counters | not run |
| `/proc/pressure/memory` | stall shares | none |

`sysctl hw.memsize` reported 8 GiB, rounded. A `meminfo` parser passed `go test -race` on a sample with invented numbers. A Linux-only reader was checked with `GOOS=linux GOARCH=arm64 go vet ./... && go build` and **never run**.

## When a service dies mysteriously

Exit code 137 is 128+9, a {{< term "sigkill" "SIGKILL" >}}, as in [Processes and signals](/posts/linux-processes-signals/). The OOM killer can cause it, but so can a person or systemd. Check `memory.events`, then the kernel log (illustrative, not captured):

```
Memory cgroup out of memory: Killed process 4242 (app)
```

## A few things to watch

- Low `free` is fine; low `available` is not.
- Compare RSS, not VSZ, with limits.
- Overcommit moves the failure later, as a kill.
- Never test OOM on a machine you care about.

## Exercise

On a throwaway Linux box, run `free` before and after `cat bigfile > /dev/null`.

## What's next

The next post is “I/O and epoll”.
