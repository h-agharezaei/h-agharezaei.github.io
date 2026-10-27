+++
date = '2027-06-07T10:00:00+03:30'
draft = false
title = 'Safe scripting and cron'
description = 'Safe shell scripting and cron on macOS: quoting, set -e traps, atomic writes, a mkdir lock and a Go cron parser with tests.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "shell", "cron", "scripting", "locking", "go"]
cover = { image = "/images/covers/linux-scripting-cron-safely.png", alt = "Safe scripting and cron", hiddenInSingle = true }
+++

This is the last post of the Linux series. After [strace and perf](/posts/linux-strace-perf/) we know how to look inside a running process; now we stop the small scripts around our services from breaking at 3 a.m. It builds on [the practical shell](/posts/linux-shell-practical/), [processes and signals](/posts/linux-processes-signals/) (for `trap`) and [systemd units and timers](/posts/linux-systemd-units-timers/).

> Honest disclaimer: everything ran on **macOS** (`/bin/sh`, `/bin/bash` 3.2, BSD tools). `flock`, `timeout` and `shellcheck` are not installed (`command -v` printed nothing), so I did not run them. I never touched my real crontab. Dangerous patterns were only `echo`ed or run in a throwaway directory.

## Classic bugs, real runs

An empty variable plus a glob is the famous disaster. I only echoed it:

```sh
dir=""; echo rm -rf $dir/*
```
```
rm -rf /Applications /Library /System ...
```

`$dir/*` became `/*`, the real top-level directories. `set -u` and `${dir:?}` stop it.

```sh
sh -c 'set -u; echo "$undefined_v"'     # /bin/sh: undefined_v: unbound variable
sh -c 'dir=""; echo "${dir:?dir is empty}/x"'   # /bin/sh: dir: dir is empty
```

Both exited with status 127. Unquoted expansion is {{< term "word-splitting" "word splitting" >}}; loop over globs, not `ls`:

```sh
for f in $(ls data); do echo "[$f]"; done    # [a] [b] [c]  (file "b c" is split)
for f in data/*;     do echo "[$f]"; done    # [data/a] [data/b c]
```

A failed `cd` does not stop a script: `cd nodir; echo "now in: $(basename "$PWD")"` printed `now in: sandbox`. Write `cd nodir || exit 1`.

`read l` trimmed `  lead  ` to `[lead]`; `IFS= read -r l` kept it. With an empty `v`, `[ $v = x ]` failed with `unary operator expected` (status 2), while bash's `[[ $v = x ]]` returned 1 cleanly; `[[ ]]` is not POSIX. Use `rm -- -n` for names starting with a dash.

## set -e surprises

`set -e` has exceptions; these are real runs:

```sh
set -e; false && echo no; echo "reached"     # reached, exit 0
set -e; f() { false; echo "in f"; }; f || echo failed   # in f  (set -e is off inside f)
set -e; ( false; echo inner ) || echo handled           # inner, handled
set -e; false | true; echo "pipe hidden"                # pipe hidden
set -eo pipefail; false | true; echo no                 # exit 1
```

So `-e` is a safety net, not a plan: check important commands explicitly.

## Temp files and atomic writes

Predictable names like `/tmp/foo` invite {{< term "race-condition" "races" >}}; use `mktemp -d` and a `trap`. To replace a file, write a temp file and `mv` it: an {{< term "atomic-write" "atomic write" >}}. My test: a writer rewrites `cfg.txt` 300 times while a reader loops.

```
naive:  reads=9   bad_reads=3
atomic: reads=220 bad_reads=0
```

Truncate-then-fill showed the reader empty files; the rename never did. Counts vary per run.

## A portable lock

For overlapping runs, `flock -n` (util-linux) is the Linux answer, docs only. Here I used atomic `mkdir` with a PID file and {{< term "lockfile" "stale-lock" >}} detection:

```
08:10:17Z pid 94781: got the lock, working for 3s
08:10:18Z pid 94786: already running as pid 94781, exiting      (exit 75)
```

A lock left by a dead PID (I faked one with `99999`) was reported as stale and taken over. Limits: two processes can still race on the takeover, and PIDs get reused. Fine for cron, not for money.

## cron itself

From `man 5 crontab` on this Mac (a Vixie-style page):

- Five fields (minute to day of week; 0 and 7 are Sunday), with ranges, lists and steps; no seconds.
- If both day fields are restricted, the command runs when **either** matches: `30 4 1,15 * 5` is the 1st, the 15th and every Friday.
- `%` becomes a newline unless written `\%`.
- Output goes to mail (`MAILTO`) unless you redirect it.
- DST shifts can skip or repeat jobs, per the BUGS section.
- The environment is minimal (`SHELL=/bin/sh`, `HOME`, `LOGNAME`); set your own `PATH`.
- Missed runs while the machine was off are not caught up; per its docs, systemd `Persistent=true` does.

I wrote a parser, next-runs calculator and linter in Go (`go test -race` passed, with these man page examples). Next runs, UTC, from Mon 2027-06-07 10:00:

```
"30 4 1,15 * 5"   Fri 06-11 04:30, Tue 06-15, Fri 06-18, Fri 06-25, Thu 07-01
"0 0 31 2 *"      never runs
"@daily"          Tue 06-08 00:00, Wed 06-09 ...
```

The linter flagged every-minute jobs, impossible dates, unescaped `%`, relative paths and unredirected output. Minute `0` makes many jobs start together (a {{< term "thundering-herd" "thundering herd" >}}), so pick odd minutes or add jitter.

## Alternatives

systemd timers offer `OnCalendar=`, `Persistent=` and `RandomizedDelaySec=`; I did not run them. A Kubernetes CronJob has a `concurrencyPolicy` field for overlap, per its docs.

## A template that combines it all

`template.sh` (about 30 lines) has `set -eu`, a fixed `PATH`, `umask 077`, `getopts`, a `-n` dry run, the `mkdir` lock, `mktemp -d` with a `trap` and UTC logs on stderr. Real runs:

```
$ sh template.sh
usage: <demo>/template.sh [-n] [-o outdir] [--] input...      (exit 2)
$ sh template.sh -n -o res in1.log "in 2.log"
2027-... dry run: would write 2 files to res                  (exit 0, no res dir)
$ sh template.sh missing.log
... cannot read missing.log                                    (exit 1, temp and lock removed)
```

## A few things to watch

- Absolute paths, a set `PATH`, and a least-privilege user; see [the filesystem and permissions](/posts/linux-filesystem-permissions/).
- Never put secrets in the script or the crontab line; see [managing secrets](/posts/sec-secrets-management/).
- Redirect output to a log and monitor the exit code. Add a {{< term "dead-mans-switch" "dead man's switch" >}}: ping a monitor after success and alert when the ping is missing.
- Make jobs {{< term "idempotency" "idempotent" >}}. Use GNU `timeout` on Linux (absent here).
- Deploy scripts follow the same rules: [designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/).

## Exercise

Start `lock.sh` twice, then `kill -9` the holder and start a third copy; read the stale-lock message.

## What's next

The Linux series ends here. Next comes the Distributed Systems series, starting with “Why distributed systems are hard” ([link](/posts/ds-why-distributed-is-hard/)). Not covered: everything came from a Mac, so I ran no real Linux kernel, containers or systemd; Linux-specific parts come from documentation and are labelled.
