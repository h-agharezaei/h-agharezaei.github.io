+++
date = '2027-06-04T10:00:00+03:30'
draft = false
title = 'strace and perf for troubleshooting'
description = 'strace and perf from the man pages: reading syscall lines and errno, -c summaries, perf stat and record, plus a Go trace parser run on invented lines.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "strace", "perf", "troubleshooting", "syscalls", "flame-graph", "go", "macos"]
cover = { image = "/images/covers/linux-strace-perf.png", alt = "strace and perf for troubleshooting", hiddenInSingle = true }
+++

I wrote this on a Mac; nothing here ran on Linux. `strace` and `perf` are Linux-only, so I could not run either. This is the thirteenth post of the Linux series, after [Logs and journalctl](/posts/linux-logs-journalctl/). Facts come from the strace(1), ptrace(2), perf-stat(1), perf-record(1) man pages and the kernel sysctl docs; Linux-looking text is labelled "illustrative, not captured". Related: [I/O and epoll](/posts/linux-io-epoll/).

## What strace shows

A {{< term "syscall" "system call" >}} is how a program asks the kernel for something. {{< term "strace" "strace" >}} prints each one with its arguments and result. The man page's own examples:

```
open("/dev/null", O_RDONLY) = 3
open("/foo/bar", O_RDONLY) = -1 ENOENT (No such file or directory)
```

A failed call returns -1 and strace appends the {{< term "errno" "errno" >}} symbol. The man page says it uses {{< term "ptrace" "ptrace" >}} and that a traced process runs more slowly, so be careful on a busy production process. I give no overhead numbers; `--seccomp-bpf` is documented as reducing the cost.

## The options I reach for

- `-f` follows children and threads (`-f -p PID` attaches to all threads).
- `-tt` adds wall-clock time with microseconds; `-T` shows time spent in each call.
- `-e trace=...` picks calls, `-p PID` attaches, `-o file` writes to a file.
- `-s N` string length (default 32); `-y` prints paths for file descriptors.
- `-k` prints a stack trace after each call; `-c` prints only a summary.

Special lines: a blocked call is `<unfinished ...>` then `<... select resumed>`; an interrupted restartable call shows `ERESTARTSYS (To be restarted)`; signals appear as `--- SIGALRM ... ---`, the end as `+++ exited with 1 +++`.

## A parser I could run

Since I cannot capture a trace, I wrote a Go parser for this format, with a `strace -c` style summary and a detector. The input is a **sample in the documented format, invented, not captured**. `go test -race` passed, and the program also passed `GOOS=linux GOARCH=arm64 go vet` and a build. Real output on the fixture:

```
$ lx13 summary testdata/sample.strace
% time     seconds  usecs/call     calls    errors syscall
 79.15    1.900900     1900900         1           futex
 20.82    0.500038       71434         7         4 read
  0.01    0.000300         300         1           execve
  ...
100.00    2.401624                    17         8 total
(1 unparsed lines skipped)
```

The `futex` row is an unfinished and resumed pair merged into one call. Real `strace -c` lays it out differently, and these numbers are invented.

```
$ lx13 detect testdata/sample.strace
FLAG: connect: connection refused (nothing listening at ...)
FLAG: 3 EAGAIN in a row on 4001/read: a non-blocking fd polled in a loop? Check for epoll
FLAG: openat "/var/lib/demo/state": EACCES, permission denied
FLAG: search path for app.conf: ENOENT in /etc/demo, /usr/local/etc/demo; found at ./app.conf
```

(Address trimmed.) The parser takes the return text after the last `) = `, so a string argument containing that sequence can fool it.

## perf

With {{< term "perf" "perf" >}}, `perf stat` counts events for a command; its man page shows cycles, instructions and an "insn per cycle" figure, and context switches. `perf record` samples stacks (`-g` enables call graphs, `-F` sets frequency, `-p` attaches) and `perf report` reads the file; `perf top` is live. Sampling is cheaper than tracing every call but can miss short events. A {{< term "flame-graph" "flame graph" >}} draws the samples; Brendan Gregg's FlameGraph scripts do this from perf output. The Go equivalent is in [Profiling Go with pprof](/posts/go-profiling-pprof/); a {{< term "cpu-profile" "CPU profile" >}} answers the same "where does time go" question.

Access is restricted. The kernel docs say `perf_event_paranoid` defaults to 2, which disallows kernel profiling for users without CAP_PERFMON. ptrace on other users' processes needs CAP_SYS_PTRACE (ptrace(2)). In a {{< term "container" "container" >}} these {{< term "linux-capabilities" "capabilities" >}} may be missing and a seccomp profile may block ptrace; I did not check any runtime's defaults. See [Users, sudo and capabilities](/posts/linux-users-sudo-capabilities/) and [cgroups and namespaces](/posts/linux-cgroups-namespaces/).

## Symptom to first command

| Symptom | First command | Look for |
|---|---|---|
| Config not found | `strace -f -e trace=openat,stat` | ENOENT along a search path |
| Hangs | `strace -p PID` | `futex`, `epoll_wait`, `read`: what it waits on |
| Connection fails | `strace -e trace=connect` | ECONNREFUSED |
| Too many open files | `strace -e trace=openat,accept` | EMFILE |
| Slow start | `strace -c -f` | many `stat` calls |
| CPU high | `perf record -g`, `perf report` | the widest frames |

## What the Mac can show

I did not run `dtruss` or `fs_usage`, which need root. `/usr/bin/time -l` on the summarizer reported a 4816896-byte maximum resident set (macOS; it varies).

## A few things to watch

- strace changes timing and can hide races.
- Read the first failure, not the last: later errors are often consequences.
- ENOENT during a search path is normal; the question is whether the final one fails.
- Traces can contain secrets from read/write buffers; do not paste them blindly.

## Exercise

On a throwaway Linux VM, run `strace -f -tt -T -o out.txt` on a short command, then `strace -c` on it, and feed `out.txt` to the parser. What did it get wrong?

## What's next

The next post is “Safe scripting and cron”.
