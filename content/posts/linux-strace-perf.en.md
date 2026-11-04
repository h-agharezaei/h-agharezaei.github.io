+++
date = '2027-06-04T10:00:00+03:30'
draft = false
title = 'strace and perf for troubleshooting'
description = 'strace and perf from the man pages: reading syscall lines and errno, -c summaries, perf stat and record, plus a Go trace parser run on invented lines.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "strace", "perf", "troubleshooting", "syscalls", "flame-graph", "go", "macos"]
cover = { image = "/images/covers/linux-strace-perf.png", alt = "strace and perf for troubleshooting", hiddenInSingle = true }
+++

A process hangs. It uses no CPU, it prints nothing, and the logs stop at a line that does not explain anything. Or it starts, fails with "config error", and does not tell you which file it looked for. You could read the source, add print statements and redeploy. But there is a faster question to ask: what is the process asking the operating system to do right now?

Every program that touches the outside world, whether it opens a file, reads a socket or waits for a lock, does it by asking the kernel. Linux has a tool that prints these requests as they happen, `strace`, and another that shows where a busy process spends its CPU time, `perf`. This post explains what each one shows and how to read it. It follows [Logs and journalctl](/posts/linux-logs-journalctl/): logs tell you what the program chose to say, and these tools tell you what it actually did. It also relates to [I/O and epoll](/posts/linux-io-epoll/), where the waiting calls we meet here come from.

Both tools are Linux-only, and this blog is written on a Mac. So I ran neither. The facts come from the man pages for strace(1), ptrace(2), perf-record(1) and perf-stat(1), and from the kernel documentation for `perf_event_paranoid`, and I checked each claim I attribute to them. Anything that looks like Linux output is labelled "illustrative" or "invented". What I did run is a Go program that parses strace-style text, on an invented sample.

## What strace shows

A {{< term "syscall" "system call" >}} is how a program asks the kernel for something it cannot do by itself: open a file, read from it, create a socket, wait. {{< term "strace" "strace" >}} runs a program (or attaches to a running one) and prints each system call with its arguments and its result. Here are two lines taken from the strace man page's own examples:

```
open("/dev/null", O_RDONLY) = 3
open("/foo/bar", O_RDONLY) = -1 ENOENT (No such file or directory)
```

Read the first line like this. The program called `open` on `/dev/null` for reading, and the kernel answered `3`, the number of the new {{< term "file-descriptor" "file descriptor" >}}. In the second line the answer is `-1`: the call failed. After it, strace prints the {{< term "errno" "errno" >}} symbol, the error code that explains the failure, here `ENOENT`, "no such file or directory", with its text. Those two lines already solve the "which file did it look for?" problem.

How does strace see all this? According to ptrace(2), the `ptrace` system call is primarily used to implement breakpoint debugging and system call tracing, and {{< term "ptrace" "ptrace" >}} is the mechanism strace builds on (the strace page itself only links to it). The cost is real. The strace man page says a traced process runs more slowly than a normal one, so be careful when you attach to a busy production process. I give no overhead numbers, because I measured none. The page also describes `--seccomp-bpf`, which lets the kernel stop the process only for the calls you selected, as a way to reduce the slowdown (it needs `-f`).

## The options I reach for

These are all from the man page:

- `-p PID` attaches to a running process, `-o file` writes the trace to a file instead of stderr, and `-e trace=...` limits the trace to the calls you name, for example `-e trace=openat,stat`.
- `-f` follows child processes. With `-f -p PID` it also attaches to all threads of a multi-threaded process, which matters for most Go and Node programs.
- `-tt` puts a wall-clock time with microseconds on each line, and `-T` shows how long each call took.
- `-s N` sets how many bytes of a string argument are printed (the default is 32), and `-y` prints the path behind a file descriptor number.
- `-k` prints a stack trace after each call, and `-c` prints only a summary table of counts, errors and time per call.

A trace has a few special line shapes too. While a call is blocked, strace shows it as `<unfinished ...>` and later prints the result on a line starting `<... name resumed>`. If a signal interrupts a call that can be restarted, you see `= ? ERESTARTSYS (To be restarted)`. Signals show up as `--- SIGALRM ... ---`, and the end as `+++ exited with 1 +++`. Knowing these shapes keeps you from being surprised by a line that does not look like a call.

## A parser I could run, on an invented trace

I could not capture a real trace here. To still show how to read one, I wrote the following in Go: a parser for the strace line format, a summary like `strace -c`, and a small detector that flags common problems. Its input is a **sample file that I invented in the documented format, not captured from any program**. `go test -race` passes, and the program also passes `GOOS=linux GOARCH=arm64 go vet ./...`. Here are some lines from the sample, so the output below makes sense:

```
openat(AT_FDCWD, "/etc/demo/app.conf", O_RDONLY) = -1 ENOENT (No such file or directory)
openat(AT_FDCWD, "/usr/local/etc/demo/app.conf", O_RDONLY) = -1 ENOENT (No such file or directory)
openat(AT_FDCWD, "./app.conf", O_RDONLY) = 3
connect(4, {sa_family=AF_INET, sin_port=htons(5432), sin_addr=inet_addr("192.0.2.10")}, 16) = -1 ECONNREFUSED (Connection refused)
read(5, 0x7ffd1, 4096) = -1 EAGAIN (Resource temporarily unavailable)    (three times in a row)
openat(AT_FDCWD, "/var/lib/demo/state", O_RDWR) = -1 EACCES (Permission denied)
futex(0x7f00, FUTEX_WAIT_PRIVATE, 0, NULL <unfinished ...>
<... futex resumed>) = 0 <1.900900>
```

(Process ids, timestamps and durations on each line are left out here; the real file has them.) The story: the program looks for its config in two places, fails twice, and finds it in the current directory. Then it tries to connect to a database and is refused. It polls a non-blocking descriptor three times and gets `EAGAIN`, "try again later", each time. It cannot open a state file. Finally one thread waits on a `futex`, the kernel primitive behind locks, for 1.9 seconds.

The first command summarizes the file like `strace -c` would. This is the real output of my program:

```
$ lx13 summary testdata/sample.strace
% time     seconds  usecs/call     calls    errors syscall
 79.15    1.900900     1900900         1           futex
 20.82    0.500038       71434         7         4 read
  0.01    0.000300         300         1           execve
  0.01    0.000250         250         1         1 connect
  0.00    0.000058          14         4         3 openat
  0.00    0.000040          40         1           write
  0.00    0.000030          30         1           socket
  0.00    0.000008           8         1           close
100.00    2.401624                    17         8 total
(1 unparsed lines skipped)
```

Each row is one kind of call, sorted by the time spent in it. Almost 80 percent of the time is a single `futex` call, which is the thread that waited 1.9 seconds, and that tells you the program was mostly *waiting*, not computing. The `read` row shows 7 calls and 4 errors: the three `EAGAIN` results plus the restarted one. Real `strace -c` lays its table out a little differently and these numbers are invented, so use this only to learn the shape. The `futex` row is an unfinished line and its resumed line merged into one call. The last line says one line of the file was not strace output and was skipped, which is the right thing for a parser to do.

The second command looks for patterns:

```
$ lx13 detect testdata/sample.strace
FLAG: connect: connection refused (nothing listening at 4, {sa_family=AF_INET, sin_port=htons(5432), sin_addr=inet_addr("192.0.2.10")}, 16)
FLAG: 3 EAGAIN in a row on 4001/read: a non-blocking fd polled in a loop? Check for epoll
FLAG: openat "/var/lib/demo/state": EACCES, permission denied
FLAG: search path for app.conf: ENOENT in /etc/demo, /usr/local/etc/demo; found at ./app.conf
(1 unparsed lines skipped)
```

Every flag points back to one of the lines above: the refused connection (the message prints the whole argument list, which is clumsy, and the address is an example one from `192.0.2.0/24`), the busy loop on `EAGAIN` (a hint to look at how the program waits, as in the epoll post), the permission error on the state file, and the config search path that failed twice before it succeeded. The last one is an example of why you read a trace as a whole: two `ENOENT`s were normal here, because the program kept searching.

One limit of my parser: it takes the result text after the last `) = ` on a line, so a string argument that happens to contain that sequence can fool it.

## perf: where does the time go?

strace answers "what is it asking for?". If the question is instead "why is my CPU at 100 percent?", you want a profiler, and on Linux that is {{< term "perf" "perf" >}}.

`perf stat command` runs a command and counts events. The perf-stat man page shows an example with cycles, instructions, an "insn per cycle" figure and context switches. `perf record` works differently: it **samples**. Many times per second it looks at what the CPU is running and records the stack (`-g` turns on call graphs, `-F` sets the frequency, `-p` attaches to a process), and `perf report` reads the result, while `perf top` shows it live. Sampling costs less than tracing every call, but it can miss events that are shorter than the sampling interval. Think of looking at a busy road once a second instead of filming it: you get a good idea of where the cars usually are, but you can miss a car that crossed between two glances.

A {{< term "flame-graph" "flame graph" >}} draws those samples so that the widest boxes are the places where most time is spent; Brendan Gregg's FlameGraph scripts can build one from perf output (I did not run them). The Go equivalent is in [Profiling Go with pprof](/posts/go-profiling-pprof/), and a {{< term "cpu-profile" "CPU profile" >}} answers the same "where does time go" question inside the language.

You will often hit permission limits. The kernel documentation says `perf_event_paranoid` defaults to 2, which disallows kernel profiling for users without `CAP_PERFMON`. And according to ptrace(2), tracing a process of another user needs `CAP_SYS_PTRACE` (the page also describes the Yama `ptrace_scope` setting, whose default of 1 limits who may attach to whom). Inside a {{< term "container" "container" >}} those {{< term "linux-capabilities" "capabilities" >}} may be missing, and a seccomp profile can block these calls too. I did not check what any container runtime does by default, so test it. The previous posts [Users, sudo and capabilities](/posts/linux-users-sudo-capabilities/) and [cgroups and namespaces: the base of containers](/posts/linux-cgroups-namespaces/) explain the background.

## From symptom to first command

This table is my own starting guide, built from what the calls mean. I did not run these commands.

| Symptom | First command | Look for |
|---|---|---|
| Config not found | `strace -f -e trace=openat,stat` | ENOENT along a search path |
| Hangs | `strace -p PID` | `futex`, `epoll_wait`, `read`: what it waits on |
| Connection fails | `strace -e trace=connect` | ECONNREFUSED |
| Too many open files | `strace -e trace=openat,accept` | EMFILE |
| Slow start | `strace -c -f` | many `stat` calls |
| CPU high | `perf record -g`, `perf report` | the widest frames |

## What the Mac can show

Nothing equivalent. I did not run `dtruss` or `fs_usage`, which I expect to need root. That is why this post has an invented trace and not a real one, and why the honest advice is to repeat the exercise below on a machine you control.

## When a trace misleads

- **Tracing changes timing.** A traced program runs slower, which can hide a race condition or create a timeout that was not there.
- **Read the first failure, not the last.** Later errors are often consequences of the first one.
- **`ENOENT` during a search is normal.** The question is whether the final attempt fails, not whether any did.
- **Traces can contain secrets.** What a program reads and writes, including passwords and tokens, appears in the argument strings (cut off at 32 bytes by default). Do not paste traces blindly into a chat or an issue.

## Exercise

On a throwaway Linux VM, run `strace -f -tt -T -o out.txt` on a short command, then `strace -c` on the same command, and feed `out.txt` to the parser. What did the parser get wrong?

## What's next

The last post is "Safe scripting and cron". These tools help you debug a service, and the scripts and scheduled jobs that surround it need to be written so that they do not fail in the first place.
