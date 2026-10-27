+++
date = '2027-04-10T10:00:00+03:30'
draft = false
title = '/proc and observing the system'
description = 'Linux /proc and system observation: what the key files hold, the macOS tools that answer the same questions, and a Go program with build tags.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "proc", "observability", "debugging", "go", "macos"]
cover = { image = "/images/covers/linux-proc-observability.png", alt = "/proc and observing the system", hiddenInSingle = true }
+++

"The server is slow" and "the process leaks" are only useful once you can look inside a running system. This is the fourth post of the Linux series, after [Processes and signals](/posts/linux-processes-signals/). Here we look at how Linux exposes its state, and which tools show the same facts elsewhere.

> Honest disclaimer: this Mac has no Linux kernel. `/proc`, `/sys`, `strace` and `perf` do not exist here, and neither do `free` or `vmstat`. Parts marked **documentation** come from the man pages (`proc(5)` and its sub-pages on man7.org), not from a run. Everything marked **ran** ran on macOS (Go 1.26, BSD userland).

## What /proc is (documentation, not run here)

{{< term "procfs" "/proc" >}} is a virtual filesystem: the kernel generates the files when you read them. According to the man pages, the useful ones are:

- `/proc/self`: a link to the opening process's own directory.
- `/proc/<pid>/status`: readable fields such as `VmPeak`, `VmRSS`, `Threads` and `FDSize`. The page itself warns that the `Vm*` values can be inaccurate.
- `/proc/<pid>/fd/`: one symbolic link per open {{< term "file-descriptor" "file descriptor" >}}. Pipes and sockets show as `type:[inode]`.
- `/proc/loadavg`: the first three fields are the {{< term "load-average" "load average" >}}, and Linux counts jobs that are runnable or waiting for disk.
- `/proc/meminfo`: system memory, including `MemAvailable`, an estimate of memory for new programs without swapping.

I could not run any of this.

## What I could observe on macOS (ran)

The same questions have BSD answers. System-wide, `top -l 1 -n 0` printed (trimmed):

```
Processes: 473 total, 10 running, 463 sleeping
Load Avg: 11.94, 7.03, 6.74
PhysMem: 7177M used (1493M wired, 2007M compressor)
```

`sysctl` reported 8 CPUs and about 8 GiB of memory. `vm_stat` counts pages of 16384 bytes. Load 11.94 on 8 cores means a busy machine, so I publish counts, no timings.

For one process I wrote a small Go program (`main.go`). It lists `/dev/fd`, which exists on macOS, opens 5 files, then closes them. It then allocates and touches 64 MiB and reads `runtime.ReadMemStats` and `syscall.Getrusage`:

```
fds: after-before = 5
fds: after close, back to start = true
heap grew by at least 64 MiB: true
sys memory from OS, MiB (rounded up to 16): 80
max RSS >= 64 MiB: true
```

I print booleans and rounded values. Trap: `ru_maxrss` is in bytes on macOS, but kilobytes on Linux according to the docs, so the code multiplies on Linux. My program also kept running, which let me inspect it from outside. `lsof -p <pid>` summarised by type:

```
0u unix, 1w REG, 2w REG, 3u IPv4, 4u KQUEUE, cwd DIR, txt REG (x2)
```

Descriptors 0-2 are the standard streams, 3 is my listening socket, and 4 is the runtime's kqueue (the poller; on Linux it would be epoll). `lsof -nP -iTCP:<port>` named the program as `LISTEN` on `127.0.0.1:<port>`, and `netstat -an | grep` showed the same line.

`sample` is installed, but my shell found a Python shim of the same name first, so I called `/usr/bin/sample`. It worked on my own `sleep` process without sudo; I did not publish its output. I did not try `fs_usage` or `dtruss`, which I expect need privileges.

## The same program for Linux (compiled, not run)

On Linux you read `/proc` directly. Two files with {{< term "build-tag" "build tags" >}} do it:

```go
//go:build linux
package main
// proc_linux.go: opens /proc/self/status, prints VmRSS, VmPeak,
// Threads, FDSize, then reads each link in /proc/self/fd
```

```go
//go:build !linux
package main
import "fmt"
func procReport() { fmt.Println("not Linux: no /proc here") }
```

On macOS the second file is used and the program printed `not Linux: no /proc here`. For the Linux file I ran `GOOS=linux GOARCH=amd64 go vet ./...` and `go build`; both passed. **I did not run that binary**, so I show no output for it.

## Debugging recipes

| Question | Linux | macOS (ran) | Linux run? |
|---|---|---|---|
| Is it overloaded? | `cat /proc/loadavg` | `uptime`, `top -l 1 -n 0` | no |
| Memory | `free -h`, `/proc/meminfo` | `vm_stat`, `top` | no |
| Leaked fds | `ls /proc/<pid>/fd` | `lsof -p <pid>` | no |
| Memory growth | `VmRSS` over time | RSS from `ps -o rss= -p <pid>` | no |
| Who listens on a port? | `ss -ltnp` | `lsof -nP -iTCP:<port>` | no |
| What is it doing? | `strace -p <pid>` | `sample <pid> 1` | no |

A general {{< term "syscall" "system call" >}} tracer is `strace`; I did not run it. {{< term "rss" "RSS" >}} is the number to watch for growth, a topic we met in [Node.js profiling and memory](/posts/node-profiling-memory-shutdown/).

## A few things to watch

- Compare load average with the number of cores.
- Check units: `ru_maxrss` is bytes on macOS and, per the docs, kilobytes on Linux.
- A descriptor count that only grows is a leak; compare before and after.
- `/proc` values are snapshots, and some are documented as approximate.
- A shim earlier in `PATH` can hide the real tool.

## Exercise

On a Linux machine, run the program built with `GOOS=linux` and compare `FDSize`, `Threads` and the `/proc/self/fd` links with what you expect. Then open ten more files and check again.

## What's next

The next post is “systemd: units and timers”.
