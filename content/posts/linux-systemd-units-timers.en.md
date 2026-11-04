+++
date = '2027-04-18T10:00:00+03:30'
draft = false
title = 'systemd: units and timers'
description = 'systemd units and timers for a Go worker: service anatomy, SIGTERM then SIGKILL, timers versus cron, hardening, and a unit linter that ran for real.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "systemd", "timers", "services", "go", "devops"]
cover = { image = "/images/covers/linux-systemd-units-timers.png", alt = "systemd: units and timers", hiddenInSingle = true }
+++

Sooner or later your Go or Node.js program has to run on a server, and "run" means more than `./app &` in a terminal. It must start when the machine boots. If it crashes at 3 a.m., it must come back without anybody logging in. When you deploy a new version, it must stop cleanly and not in the middle of a job. And the nightly report must run every night, even if the server was off at the time. On most Linux distributions, {{< term "systemd" "systemd" >}} is what does all of this.

This post follows [/proc and observing the system](/posts/linux-proc-observability/) in the Linux series: there we looked at processes, here we see who starts, restarts and schedules them. The core idea is small. With systemd you do not write a script that starts your program and watches it. You write a short text file that *declares* what the program is and how it should live, and systemd, as the supervisor, makes it so.

> I wrote this on a Mac; nothing here ran on Linux. systemd, `systemctl` and `journalctl` do not exist on this machine, and Docker stayed off. Facts about systemd come from the freedesktop.org man pages (systemd.service, systemd.timer, systemd.exec, systemd.kill, systemd.time), and I mark them as documentation. What ran is marked **ran**: a Python linter, and a Go program that was only cross-compiled for Linux and never executed.

## What systemd manages

systemd is PID 1, the first process the kernel starts; it starts and supervises everything else. Everything it manages is called a **unit**, and each unit is described by a {{< term "unit-file" "unit file" >}}, a small INI-style text file. The file suffix gives the unit's type: `.service` (a process), `.timer` (a schedule), `.socket`, `.target` (a group of units, such as "the system is fully booted"), `.mount` and `.path`. For this post we need two: `.service` and `.timer`.

## Anatomy of a service

Here is `good/worker.service`, the unit file for a small Go worker (the worker is in the spirit of [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/)). Read it first, and then we go through it line by line:

```ini
[Unit]
Description=Example batch worker
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart=/opt/worker/worker
Restart=on-failure
RestartSec=5
User=worker
WorkingDirectory=/opt/worker
EnvironmentFile=-/etc/worker/worker.env
TimeoutStopSec=30
KillSignal=SIGTERM
NoNewPrivileges=yes
ProtectSystem=strict
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

The file has three sections. `[Unit]` says what this unit is and how it relates to others, `[Service]` says how to run the process, and `[Install]` says what happens when you enable the unit. According to the man pages:

- `After=` is ordering only: "start after that unit". It does not start the other unit. `Wants=` pulls the other unit in softly (if it fails, we still start), `Requires=` pulls it in hard. That is why the file has both.
- `Type=` says when systemd considers the service started. `simple` means "right after the process is forked", `exec` means "after the program was really executed", so a missing binary or a non-existent `User=` is reported as a failure. The man page recommends `exec` for long-running services. `notify` waits until the service tells systemd it is ready, and `oneshot` is for programs that run and exit.
- `ExecStart=` is the command. Its first word must be an absolute path, or a bare file name that systemd looks up in its own fixed list of directories. An absolute path is the safe choice.
- `Restart=on-failure` restarts the service after an unclean exit: a non-zero exit code, a signal, or a timeout. `RestartSec=` is the pause before restarting; the default is 100 ms, per the docs.
- `User=` and `WorkingDirectory=` say who runs the program and where. `EnvironmentFile=-path` loads environment variables from a file, and the dash means a missing file is not an error.
- `[Install]` matters only for `systemctl enable`: `WantedBy=multi-user.target` links the unit into the normal boot, so it starts every time the machine boots.

## Stopping: SIGTERM, then SIGKILL

Starting is the easy half. When you stop a service (or deploy a new version), systemd sends {{< term "sigterm" "SIGTERM" >}} (or whatever `KillSignal=` says), waits up to `TimeoutStopSec=`, and if processes remain it sends {{< term "sigkill" "SIGKILL" >}}. We saw in [Processes and signals](/posts/linux-processes-signals/) what that means: SIGTERM can be caught and used for cleanup, and SIGKILL cannot. So the worker must handle SIGTERM.

My `main.go` does it with `signal.NotifyContext` on `syscall.SIGTERM`: it prints `worker: started`, does a "batch" every 5 seconds, and when the signal arrives it prints a line and returns, with exit code 0. That is a {{< term "graceful-shutdown" "graceful shutdown" >}}. Set `TimeoutStopSec=` longer than your slowest batch, otherwise systemd kills the worker in the middle of a job anyway.

**Ran:** `GOOS=linux GOARCH=arm64 go vet ./...` and `go build` passed, and `file` said the result was an ELF executable for aarch64. **I never ran that binary**, and I did not run it under systemd, so I cannot show what `systemctl stop worker` prints.

## Timers

For a nightly job you could use cron, but systemd has its own tool. A `.timer` unit does not run anything itself: it *activates* the service with the same name (`foo.timer` starts `foo.service`, unless `Unit=` says otherwise). The job lives in a service, and the timer says when. From `good/worker-report.timer`:

```ini
[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=5min
```

- `OnCalendar=` is wall-clock time. `*-*-* 03:00:00` reads "any year, month and day, at 03:00:00", so every night at 3. systemd.time(7) also defines shorthands: `minutely` is `*-*-* *:*:00`, `hourly` is `*-*-* *:00:00`, `daily` is `*-*-* 00:00:00` and `weekly` is `Mon *-*-* 00:00:00`. The tool `systemd-analyze calendar` checks an expression; I could not run it.
- `OnBootSec=` and `OnUnitActiveSec=` are relative times: since boot, and since the unit was last activated.
- `Persistent=true` runs a job that was missed while the machine was off, as soon as it is back. It only has an effect on `OnCalendar=` timers.
- `RandomizedDelaySec=` adds a random delay up to that value, which spreads the load when many machines share the same schedule. `AccuracySec=` (default one minute) lets systemd group wake-ups together, so timers are not exact to the second.

The service that a timer activates is usually `Type=oneshot`: it runs the job and exits. (In `good/worker-report.service`, the ExecStart is `/opt/worker/report` and `Restart=no`.) Compared with {{< term "cron" "cron" >}}, timers add catch-up after downtime, dependencies, logs per unit and `systemctl list-timers`; cron is simpler, shorter to write and works on systems without systemd. Neither is "better" for every case.

## Hardening and logs

Because a unit file is declarative, it can also limit what the service may do. According to systemd.exec: `NoNewPrivileges=yes` blocks the process from gaining privileges (for example through setuid files), `ProtectSystem=strict` makes the filesystem read-only except for paths you allow with `ReadWritePaths=`, `PrivateTmp=yes` gives the service its own private `/tmp`, and `DynamicUser=yes` allocates a temporary user and implies several of these. Anything the service writes to stdout or stderr goes to the {{< term "journald" "journal" >}}, which you read with `journalctl -u worker`.

The day-to-day commands: after editing a unit, run `systemctl daemon-reload` so systemd re-reads it, then `systemctl start|stop|enable|status worker`. **I ran none of these.**

## A linter that ran

Since I could not run systemd, I wrote a toy checker to at least catch typical mistakes. `unitlint.py` parses a unit (including duplicate keys and `\` line continuations) and checks a few rules. On the three good files (**ran**):

```
good/worker-report.service: ok
good/worker-report.timer: ok
good/worker.service: ok
```

On two deliberately broken units, `bad/api.service` and `bad/cleanup.timer`:

```
bad/api.service: 4 finding(s)
  - ExecStart is not an absolute path: api --port 8080
  - Restart not set (service stays down after a crash)
  - no [Install]: `systemctl enable` has no effect
  - Environment given more than once (valid; all are applied)
bad/cleanup.timer: 2 finding(s)
  - matching service not found: cleanup.service
  - no [Install] WantedBy=timers.target
```

The first service has a bare `api` as the command, no `Restart=` and no `[Install]`; the last finding is only a note, because repeated `Environment=` lines are valid. The timer points at a service that does not exist next to it and cannot be enabled. Two honest limits: the absolute-path rule is stricter than systemd, which also accepts bare names that it can find in its standard directories. And the tool is a toy next to `systemd-analyze verify`, which I could not run. I skipped an OnCalendar evaluator because I could not test it against real systemd.

## Unit file traps

- `After=` does not start anything; combine it with `Wants=` or `Requires=`.
- Without a SIGTERM handler, every stop ends with SIGKILL after the timeout, so cleanup never runs.
- After editing a unit, run `daemon-reload`. If you forget it, systemd keeps running the old definition.
- Timers fire late by design (`AccuracySec=`); do not use them where the exact second matters.
- Hardening can break a service that writes outside the allowed paths; add options step by step and test after each.

## Exercise

On a Linux machine, install the example worker as a service, run `systemctl stop` and read the journal. Does it exit before the timeout? Then add a timer with `OnCalendar=minutely`, check it with `systemd-analyze calendar`, and look at it with `systemctl list-timers`.

## What's next

Next: “cgroups and namespaces: the base of containers”, because systemd's limits and isolation options are built on how the kernel limits what a service can see and use.
