+++
date = '2027-05-02T10:00:00+03:30'
draft = false
title = 'Memory, the page cache and the OOM killer'
description = 'Linux memory explained from man pages: free vs available, the page cache, overcommit, OOM scores and cgroup limits, plus a Go program that runs on macOS.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "memory", "page-cache", "oom-killer", "go", "macos"]
cover = { image = "/images/covers/linux-memory-page-cache-oom.png", alt = "Memory, the page cache and the OOM killer", hiddenInSingle = true }
+++

Two things about Linux memory scare people. The first: you run `free` on a server with 16 GB of RAM and see only a few hundred MB "free". The second: a container's main process disappears with exit code 137, even though the host has plenty of memory left. The first one is almost never a problem. The second one is. This post is about telling them apart.

It continues [cgroups and namespaces: the base of containers](/posts/linux-cgroups-namespaces/), where we saw that a cgroup's `memory.max` ends in an OOM kill. As there, I wrote this on a Mac, not on Linux. The facts come from the man pages and kernel documentation (I saved copies of them while working), and anything that looks like Linux output is labelled "illustrative, not captured". The one program that really ran, a Go program that allocates memory, ran on macOS, and I say what that does and does not show.

## Why `free` looks scary and is not

Linux does not leave RAM idle. When a program reads a file, the kernel keeps the data in memory, in what is called the {{< term "page-cache" "page cache" >}}, so the next read does not have to go to disk. Over time almost all spare RAM fills up with cache. That is by design. When a program needs memory, the kernel gives the cache pages back.

So "free" memory is the wrong thing to look at. The right question is: how much could a new program get without swapping? Linux has a number for exactly that. According to proc_meminfo(5), `MemAvailable` is an estimate of how much memory is available for starting new applications, without swapping, and `Cached` is the in-memory cache for files read from the disk, the page cache. free(1) builds its columns from `/proc/meminfo` like this:

- `used` is total minus available.
- `free` is memory that is completely unused (`MemFree`).
- `buff/cache` is buffers plus cache.
- `available` is the estimate above.

Here is an illustration. Suppose a 16 GB machine shows 300 MB `free`, 9 GB `buff/cache` and 10 GB `available`. It looks nearly full if you read the first number, and it is perfectly healthy if you read the last. (These numbers are made up to show the reading, not captured.) Judge a machine by `available`.

The cache also explains a speed difference. The first time you read a big file, the data comes from disk and fills the cache. The second time, it can come straight from memory. I could not measure it on this Mac, so I only state it as the documented behaviour.

Writes use the cache too. A write lands in memory first and goes to disk a bit later. `Dirty` is memory that is waiting to be written to the disk, and `Writeback` is memory that is being written right now. The sysctls `vm.dirty_background_ratio` and `vm.dirty_ratio` control when this flushing starts.

## Swap, overcommit and the three sizes of a process

Two more ideas help before we get to the killer.

{{< term "swap" "Swap" >}} is disk space the kernel can use to park rarely used memory pages, so RAM can serve something else. You see it in `SwapTotal` and `SwapFree`.

{{< term "overcommit" "Overcommit" >}} means the kernel may promise more memory than it really has, betting that programs will not use all of it. It is controlled by `vm.overcommit_memory`. The docs describe three values: 0 is the default heuristic, which refuses only obviously wild requests; 1 always allows; 2 never overcommits. `CommitLimit` and `Committed_AS` in `/proc/meminfo` show the limit and what has been promised so far. The important consequence: with overcommit, a `malloc` can succeed today and the failure comes later, when the program actually touches the memory. That later failure is not an error code. It is a kill.

A single process also has several "sizes", and people often compare the wrong one with the limit:

| Name | Meaning | Where to read it |
|---|---|---|
| VSZ | virtual size: everything the process has asked for, mostly never touched | `VmSize` in `/proc/<pid>/status` |
| {{< term "rss" "RSS" >}} | the pages that are actually in RAM right now | `VmRSS` |
| PSS | RSS, but pages shared with other processes are divided among the processes sharing them | `Pss` in `/proc/<pid>/smaps` |

## Allocated is not resident

The difference between VSZ and RSS is easy to see with a small experiment. The Go program in my demo directory allocates four slices of 64 MiB, then writes one byte into every 4096-byte page of each slice, one slice at a time. After every step it prints the Go runtime's own counters, and next to them the peak RSS that the operating system reports through `getrusage`. This is a real run, on macOS, and it prints only byte counts, no timings. The columns mean:

- `HeapAlloc`: bytes of live objects in the Go heap.
- `HeapSys`: heap memory the Go runtime obtained from the OS.
- `Sys`: all memory the runtime obtained from the OS.
- `maxRSS`: the peak resident size the OS reports for the process.

```
start                  HeapAlloc=   0 MiB  HeapSys=   7 MiB  Sys=  11 MiB  maxRSS=   4 MiB
allocated 1 x 64 MiB   HeapAlloc=  64 MiB  HeapSys=  71 MiB  Sys=  76 MiB  maxRSS=   5 MiB
allocated 2 x 64 MiB   HeapAlloc= 128 MiB  HeapSys= 135 MiB  Sys= 140 MiB  maxRSS=   5 MiB
allocated 3 x 64 MiB   HeapAlloc= 192 MiB  HeapSys= 199 MiB  Sys= 204 MiB  maxRSS=   5 MiB
allocated 4 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS=   5 MiB
touched   1 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS=  69 MiB
touched   2 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS= 133 MiB
touched   3 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS= 197 MiB
touched   4 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS= 261 MiB
after drop + GC        HeapAlloc=   0 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS= 261 MiB
```

Read it in three parts. In the `allocated` lines the heap grows by 64 MiB each step, yet `maxRSS` stays around 5 MiB. The program has asked for 256 MiB and the OS has handed out almost none of it, because nobody has written to those pages yet. In the `touched` lines `maxRSS` grows by about 64 MiB per slice, because now the pages really are resident. In the last line the {{< term "garbage-collector" "garbage collector" >}} has freed the slices, so `HeapAlloc` is 0, but `HeapSys` and `Sys` stay: Go keeps the memory for reuse, and `maxRSS` is a peak, so it never goes down. (`ru_maxrss` is in bytes on macOS and, I believe, in kilobytes on Linux; the demo code converts accordingly.)

This is the same gap as VSZ versus RSS. As I understand it, this is why a limit like `memory.max` is reached by pages a program has touched, not by the ones it has only requested.

## Who gets killed

When memory really runs out, the {{< term "oom-killer" "OOM killer" >}} picks a victim. The man pages describe how it chooses. `/proc/<pid>/oom_score` shows the current score: a higher score means the process is more likely to be picked, and the score is based mainly on how much memory the process uses. Next to it, `/proc/<pid>/oom_score_adj` lets you push the choice. It takes values from -1000 to +1000 and is added to the score; -1000 switches OOM killing off for that task. In other words, the biggest process tends to be the victim, not the one that asked for the last byte.

## Containers: killed while the host has free memory

Now the second scary thing. A {{< term "cgroup" "cgroup" >}} has its own limit, and the kernel checks it separately from the whole machine. According to the cgroup v2 docs:

- `memory.max` is the hard limit. If the group's usage reaches it and cannot be reduced, the OOM killer is invoked inside that cgroup.
- `memory.high` is a throttle. Going over it slows the group down with heavy reclaim pressure, but it "never invokes the OOM killer".
- `memory.events` counts what happened, including `oom_kill`, the number of processes in the cgroup killed by any kind of OOM killer.
- `memory.stat` breaks the group's memory into kinds, for example `anon` (memory not backed by a file, like heap and stack) and `file` (cached file data).

That is how a container can die while the host looks fine: the host's `available` is large, but this one group hit its own wall. The "cannot be reduced" part is important too. As I understand it, clean cache pages can be dropped to make room, so cache alone is not what kills a container. What kills it is anonymous memory and other pages the kernel cannot free.

For a gentler warning than a kill, `/proc/pressure/memory` (PSI, pressure stall information) reports `some` and `full` lines: the share of time in which some, or all, non-idle tasks were stalled waiting for memory.

Go programs have their own knob. According to the `runtime` docs, `GOMEMLIMIT` is a soft limit that covers the Go heap and the memory the runtime manages, not external memory. Setting it a bit below the container limit is common practice, so the garbage collector works harder before the kernel steps in. The Go side is covered in [The Go scheduler and garbage collector](/posts/go-scheduler-gc-internals/).

## Linux tools and what I ran

| Tool | What it shows | On this Mac |
|---|---|---|
| `free` | used, available, cache | not run (`vm_stat` exists here and reports a 16384-byte page size) |
| `/proc/meminfo` | the fields above | does not exist |
| `vmstat` | swap and paging counters | not run |
| `/proc/pressure/memory` | stall shares | does not exist |

Two more checks. The demo has a small `/proc/meminfo` parser, and its test passes under `go test -race`; the test uses a sample with invented numbers, not a real Linux machine's. A Linux-only reader that uses the parser was cross-compiled (`GOOS=linux go vet` and `go build`), and I **never ran it**.

## When a service dies mysteriously

Exit code 137 is 128 + 9: the process ended because of signal 9, {{< term "sigkill" "SIGKILL" >}}, as in [Processes and signals](/posts/linux-processes-signals/). The OOM killer can send it, but so can a person running `kill -9` or a supervisor like systemd. So do not conclude "OOM" from 137 alone. Check the group's `memory.events` for a growing `oom_kill`, then look in the kernel log for a line like this (illustrative, not captured):

```
Memory cgroup out of memory: Killed process 4242 (app)
```

## Common misreadings

- **Low `free` is fine; low `available` is not.** The first is cache doing its job, the second means real pressure.
- **Compare RSS, not VSZ, with a limit.** VSZ counts memory that was never touched and can be huge for a healthy process.
- **Overcommit moves the failure later.** A successful allocation is a promise, not a guarantee. The failure arrives as a kill, not as an error from `malloc`.
- **Never test OOM on a machine you care about.** The victim may not be the process you aimed at.

## Exercise

On a throwaway Linux machine, run `free`, then `cat bigfile > /dev/null` on a file that is large but fits in RAM, then `free` again. Which columns changed, and did `available` change much? Run `cat bigfile > /dev/null` a second time and see if it finishes faster.

## What's next

The next post is "I/O and epoll". We have seen what happens when memory runs out; now we look at how a single thread can wait on thousands of connections without using up a thread, and therefore memory, for each of them.
