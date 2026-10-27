+++
date = '2027-04-03T10:00:00+03:30'
draft = false
title = 'Processes and signals'
description = 'Linux processes and signals with real runs: exit codes 128+N, trap and cleanup, SIGKILL, zombies, process groups, SIGPIPE and Go graceful shutdown.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "processes", "signals", "trap", "shell", "graceful-shutdown"]
cover = { image = "/images/covers/linux-processes-signals.png", alt = "Processes and signals", hiddenInSingle = true }
+++

A server cut off mid-request, or a script that leaves temp files behind, usually has a signal problem. This is the third post of the Linux series, after [the filesystem and permissions](/posts/linux-filesystem-permissions/) and [the practical shell](/posts/linux-shell-practical/). Here we meet processes and their signals.

> Honest disclaimer: everything ran on **macOS** (Darwin, bash 3.2, Python 3.14, Go 1.26), not on Linux. I did not run `/proc`, `strace`, cgroups or systemd, and signal lists may differ on Linux. Pids are not shown (I print relationships instead).

## A process and its children

A {{< term "process" "process" >}} is a running program with a pid and a parent. In a script, `$$` is the shell's own pid and `$!` is the pid of the last background job.

```sh
sleep 30 &
c1=$!
```

Asking `ps -o pid,ppid,pgid,stat` about the script and its child, and printing only comparisons, gave:

```
is_script=yes parent_is_script=no  same_group_as_script=yes state=S
is_script=no  parent_is_script=yes same_group_as_script=yes state=S
```

The child's parent is the script, and both share one process group. `wait $c1` returns the child's exit status.

## Signals and exit codes

A {{< term "signal" "signal" >}} is a small asynchronous message to a process. `kill` does not necessarily kill: it only sends one. Here `kill -l` lists 31 signals, including `SIGEMT` and `SIGINFO`; `SIGUSR1` is 30 here, and I believe Linux numbers it differently, so use names.

When a signal ends a process, shells report `128 + N`. I sent `kill` (a {{< term "sigterm" "SIGTERM" >}}, signal 15) to a background sleep and `wait` returned `143`; `kill -INT` on a script ended with `130` (128+2); `kill -KILL` gave `137`. That is the {{< term "exit-status" "exit status" >}} again, now with a meaning.

One surprise: my first `kill -INT` hung, because a non-interactive shell starts `&` jobs with SIGINT ignored (POSIX, as far as I know). `set -m` fixed it.

## trap: cleanup that always runs

`trap` registers a handler. This script makes a work directory and removes it on exit:

```sh
tmp=$(mktemp -d "$PWD/work.XXXXXX")
cleanup() { echo "cleanup: removing temp dir ($1)"; rm -rf "$tmp"; }
trap 'cleanup EXIT' EXIT
trap 'echo "got TERM"; exit 143' TERM
trap 'echo "got USR1"' USR1
trap 'echo "got HUP"' HUP
echo ready
while :; do sleep 0.2; done
```

I started it in the background and sent USR1, HUP, then TERM:

```
ready
got HUP
got USR1
got TERM
cleanup: removing temp dir (EXIT)
exit=143
```

Then `exit` triggered the EXIT trap. With `kill -INT` it printed `got INT`, cleaned up and exited `130`.

## SIGKILL cannot be caught

```
ready
KILL exit=137
```

No handler line, no cleanup: the work directory stayed on disk (I deleted it). {{< term "sigkill" "SIGKILL" >}} and SIGSTOP cannot be caught or ignored, so the process never gets to run its handler.

## Zombies, groups and nohup

A child that exits stays in the process table until its parent calls `wait`; that leftover is a {{< term "zombie-process" "zombie" >}}. I made one on purpose with Python: fork, child exits with 7, parent sleeps.

```
before wait: Z (Z = zombie)
reaped: 7
after wait: ps shows ''
```

After `os.waitpid` the zombie vanished and I got exit code 7. Thousands mean a parent that never reaps.

Processes belong to a {{< term "process-group" "process group" >}}, and a signal can go to the whole group. `setsid` does not exist on this Mac, so I used Python's `start_new_session`. A shell ran `sleep 30 & sleep 30 & wait`; `ps -g` counted 3 processes. After `os.killpg(pgid, SIGTERM)` (shell form: `kill -- -PGID`) it counted 0 and the leader's status was `-15`.

`nohup` sets SIGHUP to be ignored, per the man page. A short job under `nohup` survived my HUP and exited 0; its own HUP `trap` did not print, which matches POSIX saying signals ignored on entry cannot be trapped. I did not check Linux.

## SIGPIPE

`yes | head -1` prints `y` and stops. `head` exits, the next write by `yes` hits a closed pipe and it gets {{< term "sigpipe" "SIGPIPE" >}}. `PIPESTATUS` showed `141 0`: 128+13 for `yes`. That is why `pipefail` can report 141 on a healthy pipeline.

## Graceful shutdown in Go

A service should finish in-flight work on SIGTERM. In Go, `signal.NotifyContext` turns the signal into a cancelled context. My demo takes 0.6 s jobs, checks the context only between jobs, and I sent SIGTERM during job 2:

```
ready
job 1 start
job 1 done
job 2 start
job 2 done
stop requested, not taking new jobs
exit=0
```

Job 2 finished, no job 3 started, exit 0. With `kill -KILL` the same program stopped after `job 2 start` and exited `137`. Real services also need a timeout; see [graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/) and [JetStream from Node.js](/posts/node-nats-jetstream/). Container runtimes and systemd send TERM then KILL. I did not run either.

## A few things to watch

- Send TERM first and KILL only as a last resort.
- Put cleanup in `trap ... EXIT`.
- 143 is TERM, 130 is INT, 137 is KILL.
- A background job in a script ignores INT unless job control is on.
- A zombie cannot be killed; its parent must reap it.

## Exercise

Write a script that makes a temp file, traps EXIT, INT and TERM, and loops. Send each signal, then `-KILL`, and see which runs leave the file behind.

## What's next

The next post is “/proc and observing the system”.
