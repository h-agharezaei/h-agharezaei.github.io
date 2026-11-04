+++
date = '2027-04-10T10:00:00+03:30'
draft = false
title = '/proc and observing the system'
description = 'Linux /proc and system observation: what the key files hold, the macOS tools that answer the same questions, and a Go program with build tags.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "proc", "observability", "debugging", "go", "macos"]
cover = { image = "/images/covers/linux-proc-observability.png", alt = "/proc and observing the system", hiddenInSingle = true }
+++

"The server is slow." "The process leaks something." These are useful sentences only until somebody asks: slow *how*, leaking *what*? To answer, you need to look inside a running system: how busy it is, how much memory each process holds, which files and sockets it has open. The kernel knows all of this. The question is how it tells us.

On Linux the answer is unusually simple: it shows its state as files. After [Processes and signals](/posts/linux-processes-signals/), where we sent signals to processes from the outside, this post is about reading what they look like from the inside. I will explain how Linux exposes its state, and which tools show the same facts elsewhere.

> Honest disclaimer: this Mac has no Linux kernel. `/proc`, `/sys`, `strace` and `perf` do not exist here, and neither do `free` or `vmstat`. Parts marked **documentation** come from the man pages (`proc(5)` and its sub-pages on man7.org), not from a run. Everything marked **ran** ran on macOS (Go 1.27, BSD userland). I show no Linux output at all.

## What /proc is (documentation, not run here)

Think of a company that, instead of giving you a report, lets you open a folder where a new document appears each time you open it, always up to date. That is {{< term "procfs" "/proc" >}}. It is a virtual filesystem: nothing is stored on disk, and the kernel generates the content of each file at the moment you read it. Because they are ordinary files, you can use `cat`, `grep` or any language's file API on them, with no special library.

According to the man pages, these are the useful entries:

- `/proc/self`: a link to the directory of the process that opens it, so a program can read its own details without knowing its pid.
- `/proc/<pid>/status`: readable fields such as `VmPeak` (peak virtual memory), `VmRSS` (memory held in RAM), `Threads` and `FDSize` (the size of the file descriptor table). The page itself warns that the `Vm*` values can be inaccurate.
- `/proc/<pid>/fd/`: one symbolic link per open {{< term "file-descriptor" "file descriptor" >}}. For pipes and sockets the link text has the form `type:[inode]`, for example `socket:[<inode>]`. Counting this directory is the classic way to find a file-descriptor leak.
- `/proc/loadavg`: the first three fields are the {{< term "load-average" "load average" >}}: roughly, the average number of tasks that wanted to run over the last 1, 5 and 15 minutes. On Linux, the man page says this includes tasks waiting for disk, not only for the CPU.
- `/proc/meminfo`: system memory, including `MemAvailable`, an estimate of how much memory new programs could use without swapping.

I could not run any of this here.

## What I could observe on macOS (ran)

The same questions have BSD answers, with other tools. System-wide, `top -l 1 -n 0` printed (trimmed):

```
Processes: 516 total, 6 running, 510 sleeping
Load Avg: 5.47, 4.41, 3.62
PhysMem: 7538M used (1979M wired, 2925M compressor)
```

The three Load Avg numbers are the 1, 5 and 15-minute averages. `sysctl hw.ncpu hw.memsize` reported 8 CPUs and 8 GiB of memory, and `vm_stat` says it counts pages of 16384 bytes. A load of 5.47 on 8 CPUs means a machine with work to do (other jobs were running here), so I publish only counts and no timings.

For one process I wrote a small Go program (`main.go`). It lists `/dev/fd`, which exists on macOS, opens 5 files and then closes them. Then it allocates and touches 64 MiB and reads `runtime.ReadMemStats` and `syscall.Getrusage`. It prints booleans and rounded values, because exact numbers differ on each run:

```
fds: after-before = 5
fds: after close, back to start = true
heap grew by at least 64 MiB: true
sys memory from OS, MiB (rounded up to 16): 80
max RSS >= 64 MiB: true
user+system CPU under 1s: true
```

Line by line: opening 5 files added 5 descriptors, and closing them returned the count to where it started. That before/after comparison is how you prove a leak or its absence, since the count itself includes a descriptor for the directory listing. The heap and the maximum RSS both reflect the 64 MiB we touched, and the Go runtime asked the OS for about 80 MiB in total. One honest note: the heap check compares a growth of 64 MiB against exactly 64 MiB, so it sits on the boundary. In seven runs of the program it printed `false` four times and `true` three times, because other small allocations and frees move the number slightly. A `>= 60 MiB` check printed `true` in eight out of eight runs of a throwaway copy.

There is one trap in this code. `ru_maxrss` (the peak RSS) is in bytes on macOS, but in kilobytes on Linux according to the docs, so the code multiplies by 1024 when `runtime.GOOS` is `linux`. The program also stays alive for a few seconds after printing, which let me inspect it from outside. `lsof -p <pid>` summarised by type and descriptor:

```
0r CHR, 1w REG, 2w REG, 3u IPv4, 4u KQUEUE, cwd DIR, txt REG (x2)
```

Descriptors 0 to 2 are the standard streams (here input from `/dev/null` and output to files), 3 is my listening socket, and 4 is the runtime's kqueue, the macOS mechanism the Go runtime uses to wait for network events (on Linux it would be epoll). `lsof -nP -iTCP:<port>` named the program as `LISTEN` on `127.0.0.1:<port>`, and `netstat -an` showed the same line. The pid and port change on every run, so I show them as placeholders.

macOS also has `sample`, which takes stack samples of a running process. I ran `/usr/bin/sample <pid> 1` on a `sleep` process I had started myself, and it worked without sudo; I do not show its output. I did not try `fs_usage` or `dtruss`, which I expect need privileges.

## The same program for Linux (compiled, not run)

On Linux the program can read `/proc` directly. Go lets us keep one file per platform with {{< term "build-tag" "build tags" >}}, special comments that make the compiler include a file only on some systems:

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

The Linux file is a summary here, not its full text. On macOS the second file is used and the program printed `not Linux: no /proc here`. For the Linux file I ran `GOOS=linux GOARCH=amd64 go vet ./...` and `go build`; both passed, and `file` identified the result as a Linux ELF executable. **I did not run that binary**, so I show no output for it.

## Debugging recipes

The table pairs each question with the Linux tool (from documentation) and what I ran on macOS.

| Question | Linux | macOS (ran) | Linux run? |
|---|---|---|---|
| Is it overloaded? | `cat /proc/loadavg` | `uptime`, `top -l 1 -n 0` | no |
| Memory | `free -h`, `/proc/meminfo` | `vm_stat`, `top` | no |
| Leaked fds | `ls /proc/<pid>/fd` | `lsof -p <pid>` | no |
| Memory growth | `VmRSS` over time | RSS from `ps -o rss= -p <pid>` | no |
| Who listens on a port? | `ss -ltnp` | `lsof -nP -iTCP:<port>` | no |
| What is it doing? | `strace -p <pid>` | `sample <pid> 1` | no |

A tool that records the {{< term "syscall" "system calls" >}} a process makes, which is how you see what it is *doing* right now, is `strace`; I did not run it. {{< term "rss" "RSS" >}} is the number to watch when you suspect a memory leak, a topic we met in [Node.js profiling and memory](/posts/node-profiling-memory-shutdown/).

## Misreading the numbers

- Compare load average with the number of cores. A load of 8 is fine on 16 cores and bad on 2.
- Check units: `ru_maxrss` is bytes on macOS and, per the docs, kilobytes on Linux.
- A descriptor count that only grows is a leak; compare the count before and after.
- `/proc` values are snapshots, and some are documented as approximate.
- A different program earlier in `PATH` can hide the real tool. On my machine `sample` resolved to a Python shim before `/usr/bin/sample`, so check with `type -a`.

## Exercise

On a Linux machine, run the program built with `GOOS=linux` and compare `FDSize`, `Threads` and the `/proc/self/fd` links with what you expect. Then open ten more files and check again.

## What's next

Next: “systemd: units and timers”, which is how these processes get started, restarted and scheduled on a server.
