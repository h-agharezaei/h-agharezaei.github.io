+++
date = '2027-04-03T10:00:00+03:30'
draft = false
title = 'Processes and signals'
description = 'Linux processes and signals with real runs: exit codes 128+N, trap and cleanup, SIGKILL, zombies, process groups, SIGPIPE and Go graceful shutdown.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "processes", "signals", "trap", "shell", "graceful-shutdown"]
cover = { image = "/images/covers/linux-processes-signals.png", alt = "Processes and signals", hiddenInSingle = true }
+++

You run `kill 4321` and the process keeps running. Or the opposite problem: a deploy restarts your service, and a half-written temp file is left behind, because the service was cut off in the middle of its work. Both are questions about *signals*: what the operating system sends to a process, what the process does with it, and what it does when it cannot ignore it.

In [the filesystem and permissions](/posts/linux-filesystem-permissions/) we looked at files, and in [the practical shell](/posts/linux-shell-practical/) at exit codes. Now we meet the thing that produces many of those exit codes: the process itself. We will see what a process is, how a signal reaches it, how a script can clean up after itself, what a zombie is, and how a Go service can finish its current job before it stops.

> Honest disclaimer: everything ran on **macOS** (Darwin, bash 3.2, Python 3.14, Go 1.27), not on Linux. I did not use `/proc`, `strace`, cgroups or systemd here, and signal lists and numbers may differ on Linux. Process ids are not shown: they change on every run, so I print relationships ("is the parent the script?") instead.

## A process and its children

A {{< term "process" "process" >}} is a running program. It has a number (the **pid**), a parent process that started it, and a few other labels we will meet in a moment. In a shell script, `$$` is the script's own pid, and `$!` is the pid of the last job you started in the background with `&`.

```sh
sleep 30 &
c1=$!
```

This starts `sleep` as a child of the script and remembers its pid in `c1`. I then asked `ps -o pid,ppid,pgid,stat` about the script and its child. The columns are the pid, the parent's pid (`ppid`), the process group id (`pgid`, explained below) and the state (`stat`, where `S` means sleeping). Pids vary from run to run, so my script printed only comparisons:

```
is_script=yes parent_is_script=no same_group_as_script=yes state=S
is_script=no parent_is_script=yes same_group_as_script=yes state=S
```

The first line describes the script itself: its parent is not the script (it is my shell), and it is in its own group. The second line is the `sleep` child: its parent *is* the script, it shares the script's process group, and it is sleeping. The script also confirmed that `$!` equals the child's pid. Finally `wait $c1` waits for the child and returns its exit status, which brings us to signals.

## Signals and exit codes

A {{< term "signal" "signal" >}} is a small message that the operating system delivers to a process at an arbitrary moment. It has a number and a name, and it carries no data: it only says "this happened". The word `kill` is misleading, because `kill` does not necessarily kill. It only *sends* a signal, and what happens next depends on the signal and on the process. By default, most signals end the process, but a process may catch some of them and run its own code instead.

On this Mac `kill -l` lists 31 signals, including BSD ones like `SIGEMT` and `SIGINFO`. Numbers differ between systems: `SIGUSR1` is 30 here (`kill -l USR1` printed `30`), while according to the signal(7) man page on Linux (x86 and ARM) it is 10, though I did not run that. The lesson is to use names, not numbers.

When a signal ends a process, shells report the exit status as `128 + N`, where N is the signal number. That is how a signal shows up as an {{< term "exit-status" "exit status" >}}, which we met in the last post. I sent `kill` (a {{< term "sigterm" "SIGTERM" >}}, signal 15, the polite "please stop") to a background `sleep` and `wait` returned `143` (128+15). `kill -KILL` gave `137` (128+9). A script stopped with `kill -INT` (signal 2, what Ctrl+C sends) ended with `130`.

That last one has a trap. In my first attempt, `kill -INT` on a background script did nothing and the script kept running. POSIX says that when job control is off, which is the case in a non-interactive shell, commands started with `&` ignore SIGINT and SIGQUIT. The script inherited "ignore INT" from its parent. With `set -m` (job control on) in the parent, `kill -INT` worked and the status was 130, as we will see below.

## trap: cleanup that always runs

A process can ask the shell to run a command when a signal arrives. That command is called a handler, and `trap` registers it. The special name `EXIT` means "when the script exits, for whatever reason". The script below makes a work directory and removes it on exit:

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

(The demo file also has a `trap` for `INT` that prints `got INT` and exits with 130.) The script creates a temporary directory, defines a cleanup function, and registers four handlers: USR1 and HUP only print a line, TERM prints and exits, and `exit` itself triggers the EXIT handler. Then it loops forever. I started it in the background and sent USR1, HUP and TERM, in that order, with a short pause between them:

```
ready
got USR1
got HUP
got TERM
cleanup: removing temp dir (EXIT)
exit=143
```

Each signal ran its handler. The script survived USR1 and HUP and kept looping, then TERM made it call `exit 143`, and that exit ran the EXIT handler, which removed the directory. This is the pattern to copy: put the cleanup in `trap ... EXIT`, and the temp directory goes away on a normal exit, on `exit` after an error and on TERM.

With job control on (`set -m` in the driver), `kill -INT` printed `got INT`, ran the cleanup and exited with `130`. Without it, the script ignored INT, as explained above, and `trap` could not change that: handlers for signals that were ignored when the shell started cannot be installed.

## SIGKILL cannot be caught

Cleanup handlers help only if the signal can be caught. {{< term "sigkill" "SIGKILL" >}} (signal 9) and SIGSTOP cannot be caught, blocked or ignored. The kernel stops the process, and the process never gets to run any of its code. Here is the same script after `kill -KILL`:

```
ready
KILL exit=137
```

There is no `got ...` line and no cleanup line, and the work directory stayed on disk (I deleted it by hand). So `SIGKILL` is the last resort: use it only after TERM has been given a fair chance, and expect leftovers.

## Zombies, groups and nohup

When a child exits, the kernel keeps a small record of it, its exit status, until the parent asks for it with `wait`. A child that has exited but has not yet been waited for is a {{< term "zombie-process" "zombie" >}}. I made one on purpose with Python: fork a child that exits at once with code 7, and let the parent sleep without waiting.

```
before wait: Z (Z = zombie)
reaped: 7
after wait: ps shows ''
```

`ps` showed state `Z` for the child. After the parent called `os.waitpid`, it got exit code 7 and the zombie vanished from `ps`. A zombie uses almost nothing, but it holds a pid, so thousands of them mean a parent that never reaps its children. You cannot kill a zombie, because it is already dead; the parent must wait for it (or die, so that someone else adopts and reaps it).

Processes also belong to a {{< term "process-group" "process group" >}}, which is how a shell treats a pipeline or a job as one unit, and a signal can be sent to the whole group. `setsid` does not exist on this Mac, so I used Python's `start_new_session`, which creates a new session and group. A shell ran `sleep 30 & sleep 30 & wait`, and `ps -g` counted 3 processes in the group. After `os.killpg(pgid, SIGTERM)` (the shell form is `kill -- -PGID`, with a minus before the group id) it counted 0 left, and the leader's status was `-15`: Python's way of saying "ended by signal 15". Killing only the leader would have left the two `sleep` children running.

The signal you meet most often in practice is SIGHUP, "the terminal went away", which is what a closed SSH session sends to its jobs. `nohup` sets SIGHUP to be ignored before starting a command, according to the man page. In my test, a short job under `nohup` survived my HUP and exited 0, and its own HUP `trap` did not print. Without `nohup` the same job printed `trapped HUP`. The first result is consistent with POSIX saying that a signal ignored on entry to a shell cannot be trapped. I did not check this on Linux.

## SIGPIPE

One more signal explains a strange exit code. `yes | head -1` prints `y` and stops, although `yes` would print forever. The reason is that `head` exits after one line. The next time `yes` writes to the pipe, nobody is reading, and the kernel sends it {{< term "sigpipe" "SIGPIPE" >}} (signal 13), which ends it. `PIPESTATUS` (bash's list of each command's status in the last pipeline) showed `141 0`: 128+13 for `yes`, and 0 for `head`. With `set -o pipefail`, the whole pipeline reported `141` even though nothing was wrong. That is why `pipefail` can report a failure on a healthy pipeline.

## Graceful shutdown in Go

Now we put signals to good use. When a service gets SIGTERM, the right thing is to finish the work that is in flight and not take new work. In Go, `signal.NotifyContext` turns the signal into a cancelled context. My demo runs 0.6-second jobs in a loop, checks the context only *between* jobs, and never interrupts a job that has started. I sent SIGTERM while job 2 was running:

```
ready
job 1 start
job 1 done
job 2 start
job 2 done
stop requested, not taking new jobs
exit=0
```

Job 2 was allowed to finish, no job 3 started, and the program exited 0. When I sent `kill -KILL` instead, the same program stopped right after `job 2 start` and the exit status was `137`: the job was cut in half, exactly the problem from the start of this post. Real services also need a timeout for jobs that never finish; see [graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/) and [JetStream from Node.js](/posts/node-nats-jetstream/). Container runtimes and systemd are documented to send TERM first and KILL after a grace period; I did not run either here.

## Where shutdowns go wrong

- Send TERM first and KILL only as a last resort. KILL skips every cleanup.
- Put cleanup in `trap ... EXIT`, so one handler covers normal exit, errors and TERM.
- Remember the codes: 143 is TERM, 130 is INT, 137 is KILL, 141 is SIGPIPE.
- A background job in a non-interactive script ignores INT unless job control is on, so Ctrl+C-style tests can mislead you.
- A zombie cannot be killed; its parent must reap it.

## Exercise

Write a script that makes a temp file, traps EXIT, INT and TERM, and loops. Send each signal, then `-KILL`, and see which runs leave the file behind.

## What's next

Next: “/proc and observing the system”, because after you can stop a process, the next question is how to look inside a running one.
