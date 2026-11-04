+++
date = '2027-06-07T10:00:00+03:30'
draft = false
title = 'Safe scripting and cron'
description = 'Safe shell scripting and cron on macOS: quoting, set -e traps, atomic writes, a mkdir lock and a Go cron parser with tests.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "shell", "cron", "scripting", "locking", "go"]
cover = { image = "/images/covers/linux-scripting-cron-safely.png", alt = "Safe scripting and cron", hiddenInSingle = true }
+++

A script works when you run it by hand. You put it in cron, and at 3 a.m. it starts failing, quietly. Nobody sees an error, because cron has no terminal to show it on. Days later someone notices that the backup has not run since the last deploy. When you finally look, the cause is small: a tool that is on your `PATH` but not on cron's, or a variable that was empty, or two runs that overlapped and overwrote each other.

This last post of the Linux series is about writing the small scripts around our services so that they fail loudly instead of silently, and about the facts of cron that surprise people. It builds on [The practical shell: pipes, redirects and xargs](/posts/linux-shell-practical/), [Processes and signals](/posts/linux-processes-signals/) (for `trap`, which we use for cleanup) and [systemd: units and timers](/posts/linux-systemd-units-timers/), the modern alternative to cron. The previous post, [strace and perf for troubleshooting](/posts/linux-strace-perf/), is what you reach for when a script still misbehaves.

> Honest disclaimer: everything here ran on **macOS**, with `/bin/sh`, `/bin/bash` (version 3.2) and BSD tools. `flock` and `shellcheck` are not installed here (`command -v` printed nothing), so I did not run them. This macOS does ship a BSD `timeout`, and I mention it below. I never touched my real crontab. Dangerous patterns were only `echo`ed, or run in a throwaway directory I created.

## Classic bugs, run for real

The first rule of a shell script is that the shell does text substitution *before* the command runs, and it does not warn you when the text is not what you meant. The famous example is an empty variable followed by a glob. I did not run the `rm`. I only printed what the shell would hand to it:

```sh
dir=""; echo rm -rf $dir/*
```
```
rm -rf /Applications /Library /System /Users /Volumes /bin /cores /...
```

The empty `$dir` vanished, `$dir/*` became `/*`, and the shell expanded that into the real top-level directories of the machine. (I cut the list, which continues with more directories.) With a real `rm -rf` this is a disaster. Two shell features stop it. `set -u` makes using an unset variable an error, and `${dir:?message}` stops the script when the variable is unset or empty:

```sh
sh -c 'set -u; echo "$undefined_v"'     # sh: undefined_v: unbound variable
sh -c 'dir=""; echo "${dir:?dir is empty}/x"'   # sh: dir: dir is empty
```

Both commands stopped with exit status 127 on this Mac. (The exact status and message wording depend on the shell.)

Next trap: **word splitting**. When you write `$var` without quotes, the shell cuts the value at spaces and treats the pieces as separate arguments. The {{< term "word-splitting" "word splitting" >}} also hits file names. Loop over globs, not over `ls` output. Here the directory has two files, `a` and `b c` (a name with a space):

```sh
for f in $(ls d2); do echo "[$f]"; done    # [a] [b] [c]     "b c" was split in two
for f in d2/*;     do echo "[$f]"; done    # [d2/a] [d2/b c]
```

The first loop saw three words, so it ran three times and never saw the real name. The second gives the shell the glob directly, and each match stays one item, space included. And always quote the variable inside: `"$f"`.

A third one: a failed `cd` does not stop a script. This is what I ran in a directory called `sandbox`:

```sh
cd nodir; echo "now in: $(basename "$PWD")"     # now in: sandbox
```

The `cd` failed, the script went on, and the next command ran in the wrong directory. If that next command had been `rm`, it would have deleted files from the wrong place. Write `cd nodir || exit 1`.

More small ones I ran:

- `read l` trims leading and trailing spaces: `  lead  ` became `[lead]`. `IFS= read -r l` kept it exactly: `[  lead  ]`. The `-r` also stops backslashes from being interpreted.
- With an empty `v`, `[ $v = x ]` becomes `[ = x ]` and fails with `unary operator expected` (status 2). Bash's `[[ $v = x ]]` returned 1 (false) cleanly. But `[[ ]]` is a bash feature, not part of POSIX `sh`, so quote variables instead: `[ "$v" = x ]`.
- A file whose name starts with a dash looks like an option. `rm -- -n` removes a file named `-n`, because `--` ends option parsing. (I tested it in the scratch directory.)

## set -e: a safety net with holes

Many people start scripts with `set -e`, which means "exit when a command fails". It helps, but it has exceptions that surprise people. Each of these is a real run on this Mac. They are one-liners passed to `sh -c`:

```sh
set -e; false && echo no; echo "reached"                 # reached          (exit 0)
set -e; f() { false; echo "in f"; }; f || echo failed    # in f             (set -e is off inside f)
set -e; ( false; echo inner ) || echo handled            # inner            (set -e is off in the subshell, too)
set -e; false | true; echo "pipe hidden"                 # pipe hidden
set -eo pipefail; false | true; echo no                  # (nothing)        exit 1
```

Line by line. In the first, a failure on the left side of `&&` is "handled", so the script does not stop. In the second, a function called as part of `f || ...` runs with `set -e` ignored, so `false` did not stop it and `in f` printed even though `false` had failed. The third is the same idea for a subshell used in a `||` list: `inner` printed, and `handled` did not, because the subshell's last command succeeded. In the fourth, the status of a pipeline is the status of its **last** command, so the failing `false` was hidden by `true`. `pipefail` fixes that: with it the pipeline fails if any part fails, and the script exited with status 1.

The lesson: `set -e` is a safety net, not a plan. Add `set -u` and, in shells that support it, `pipefail`, and still check the important commands explicitly.

## Temporary files and atomic writes

Two scripts that use the same fixed temp file name, such as `/tmp/foo`, can step on each other, and a predictable name invites {{< term "race-condition" "race conditions" >}} and attacks. Use `mktemp -d` to make a private directory and a `trap` to delete it when the script exits.

A related problem: you want to replace a config file that other programs read. If you truncate the file and then write the new content, a reader that looks in between sees an empty or half-written file. The fix is an {{< term "atomic-write" "atomic write" >}}: write the new content to a temp file in the same directory, and then `mv` it over the old one. On one filesystem, the rename is atomic, so a reader sees either the old file or the new one, never something in between.

I tested this with `atomic.sh`: a writer rewrites `cfg.txt` 300 times, once in the naive way (truncate, then fill) and once with write-then-rename, while a reader loops and reads the file as fast as it can. It counts a read as bad if the content does not look complete. Real output of one run:

```
naive:  reads=8   bad_reads=6
atomic: reads=216 bad_reads=0
```

In the naive mode, most reads caught the file empty. In the atomic mode, none did. The counts change on every run (I ran each mode three times: the naive mode had 5 or 6 bad reads out of 8 or 9 every time, the atomic mode always had 0), and this machine was busy. The total number of reads differs between the two modes simply because the two writers take different amounts of time. So only the comparison of zero bad reads against many means anything.

## A lock that works on macOS and Linux

If a script runs every minute and one run sometimes takes two minutes, two copies will overlap. The usual answer on Linux is `flock -n` from util-linux. According to its man page, flock manages `flock(2)` locks from the shell, and `-n` makes it fail instead of waiting when the lock is taken. `flock` is **Linux-only**, and I did not run it here.

On macOS (and any POSIX system) you can use something that every system has: `mkdir`. Creating a directory is atomic, so exactly one process can succeed in creating it. My `lock.sh` makes a lock directory, writes its pid inside, and removes the directory on exit with a `trap`. If the directory already exists, it checks whether the pid inside is still alive (`kill -0` sends no signal, it only checks). I started one copy that worked for 3 seconds and, a second later, another one:

```
<utc-time> pid 80555: got the lock, working for 3s
<utc-time> pid 80560: already running as pid 80555, exiting       (exit status 75)
<utc-time> pid 80555: done
```

The second run saw a live owner and exited with 75 (the "temporary failure" code from `sysexits.h`; the number itself is my choice). The pids differ on each run. To test the dead-owner case, I created a lock directory whose pid file said `99999`, a pid that was not running, and started the script:

```
<utc-time> pid 80569: stale lock (pid 99999 is gone), taking over
<utc-time> pid 80569: got the lock, working for 1s
<utc-time> pid 80569: done
```

It noticed the owner was gone, called the lock stale, took it over and finished. This lock has limits. Two processes can still race during the takeover (the script tries to notice by checking `mkdir` again), and process ids get reused, so a dead owner's pid could belong to an unrelated process later. That is fine for a nightly job, and not good enough to protect money.

## cron itself

Now cron. These facts come from `man 5 crontab` on this Mac, which is a Vixie-style page. A Linux distribution's page may differ in details, so check yours.

- A line has five time fields: minute, hour, day of month, month, day of week (0 and 7 are both Sunday), then the command. Fields accept ranges, lists and steps. There are no seconds.
- If **both** day fields (day of month and day of week) are restricted, the command runs when **either** matches. So `30 4 1,15 * 5` runs on the 1st, on the 15th, and on every Friday, not only on Fridays that are the 1st or 15th.
- A `%` in the command is turned into a newline (and what follows is sent to the command as input), unless you write `\%`. This breaks `date +%F` in a crontab, which is a classic trap.
- Output is mailed to the owner, or to `MAILTO`, unless you redirect it. With an empty `MAILTO=""` no mail is sent.
- The page's BUGS section warns that jobs scheduled during a daylight-saving change are affected, so avoid scheduling jobs in that window.
- The environment is minimal. This page lists three variables that cron sets: `SHELL` (as `/bin/sh`), `LOGNAME` and `HOME`. It does not say what `PATH` is, so set your own at the top of the crontab or in the script.
- This page does not mention catching up on runs missed while the machine was off. A systemd timer with `Persistent=true` does catch up, according to systemd.timer.

To feel the "minimal environment" problem, I simulated it with `env -i`, which starts a command with an empty environment and then I added the three variables. This is **not** cron, only a stand-in:

```
$ env -i SHELL=/bin/sh LOGNAME=demo HOME=/nonexistent /bin/sh -c 'echo "PATH=[$PATH]"; command -v go || echo "go: not found"'
PATH=[/usr/gnu/bin:/usr/local/bin:/bin:/usr/bin:.]
go: not found
```

In my normal shell `go` is found, under `/opt/homebrew/bin`. With a bare environment the shell falls back to its own built-in default `PATH`, which does not include that directory, and the command is not found. A script that works for you and not in cron looks exactly like this. The built-in default `PATH` is this shell's, and cron's value may be different, so do not copy that line as a fact about cron.

I also wrote a cron expression parser, a "next runs" calculator and a linter in Go. Its tests (`go test -race` passes) include examples from the man page. Here are the next runs in UTC, counted from Monday 2027-06-07 10:00:

```
"30 4 1,15 * 5"   Fri 2027-06-11 04:30, Tue 06-15, Fri 06-18, Fri 06-25, Thu 07-01
"0 0 31 2 *"      never runs
"@daily"          Tue 2027-06-08 00:00, Wed 06-09, Thu 06-10, ...
```

(Shortened: the real output prints each time on its own line, with the year and `UTC`.) The first line is the either/or rule at work: Friday the 11th, then Tuesday the 15th (a day-of-month match), then Fridays. The second is an impossible date, February 31st, and the program says so instead of looping forever. For a full crontab line, the linter looks for common mistakes. This is the real output for `0 3 * * * backup.sh`:

```
  WARN: minute 0: many jobs start together; pick an odd minute
  WARN: command backup.sh has no absolute path; cron's PATH is minimal
  WARN: output is not redirected; cron will mail it (or drop it)
```

The minute-0 warning is advice of mine, not a cron rule: if every team schedules jobs at minute 0, the machine gets a burst of work at once, so pick an odd minute or add a small random delay.

## Alternatives to cron

A systemd timer has `OnCalendar=` for calendar times, `Persistent=` to catch up on runs missed while the machine was off, and `RandomizedDelaySec=` to spread jobs out, all according to systemd.timer. I did not run them here. And a Kubernetes CronJob has a `concurrencyPolicy` field (`Allow`, `Forbid` or `Replace`) that says what to do when the previous run is still going, so you do not need your own lock there, according to its docs.

## A template that combines it all

I put the practices together in `template.sh` (about 30 lines of POSIX `sh`). It has `set -eu`, a fixed `PATH`, `umask 077`, option parsing with `getopts`, a `-n` dry-run flag, the `mkdir` lock, a `mktemp -d` work directory with a `trap`, and log lines in UTC on stderr. For the test, the script counts the lines of its input files and writes the counts to an output directory. Real runs, with the script path replaced by `<demo>`:

```
$ sh template.sh
usage: <demo>/template.sh [-n] [-o outdir] [--] input...      (exit 2)
$ sh template.sh -n -o res in1.log "in 2.log"
<utc-time> dry run: would write 2 files to res                (exit 0, no res directory)
$ sh template.sh missing.log
<utc-time> cannot read missing.log                            (exit 1, temp dir and lock removed)
```

The first run, with no arguments, prints usage and exits with 2. The second is a dry run: it did the work in the temp directory, said what it would write, and left no `res` directory behind. The third failed on a missing input, and I checked that the `trap` had cleaned up both the temp directory and the lock. I also ran it for real once, and it wrote `res/in1.log.count` and `res/in 2.log.count` (the file with a space in its name worked because every variable is quoted). And I checked all three scripts with `sh -n`, which only parses them and reports syntax errors.

## Before you schedule a script

- **Absolute paths, a set `PATH` and a least-privilege user.** See [The filesystem and permissions](/posts/linux-filesystem-permissions/).
- **No secrets in the script or the crontab line.** Anyone who can read them can read the secret. See [Managing secrets and keys](/posts/sec-secrets-management/).
- **Redirect output and watch the exit code.** Add a {{< term "dead-mans-switch" "dead man's switch" >}}: the job pings a monitoring service after it succeeds, and the monitor alerts you when the ping is missing. That catches the "cron did not run at all" case that no error log can.
- **Make the job {{< term "idempotency" "idempotent" >}}.** Running it twice should give the same result as running it once, so a retry or an overlap does no harm.
- **Limit the runtime.** This macOS has a BSD `timeout` (`timeout 1 sleep 5` ended with status 124, which its man page documents as the timed-out status). On Linux, GNU `timeout` is the usual tool, and I did not run it here; its options differ a little from the BSD one.
- **Deploy scripts follow the same rules.** See [Designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/).

## Exercise

Start `lock.sh` twice in two terminals, then `kill -9` the one that holds the lock and start a third copy. Read the stale-lock message and think about what could go wrong if the pid had been reused.

## What's next

The Linux series ends here. The Distributed Systems series starts with "Why distributed systems are hard" ([link](/posts/ds-why-distributed-is-hard/)), where the problems of one machine become the problems of many. One more honest note about this whole series: everything was written on a Mac, so I ran no real Linux kernel, containers or systemd. The Linux-specific parts come from documentation and are labelled.
