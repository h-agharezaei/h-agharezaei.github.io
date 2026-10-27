+++
date = '2027-04-18T10:00:00+03:30'
draft = false
title = 'systemd: units and timers'
description = 'systemd units and timers for a Go worker: service anatomy, SIGTERM then SIGKILL, timers versus cron, hardening, and a unit linter that ran for real.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "systemd", "timers", "services", "go", "devops"]
cover = { image = "/images/covers/linux-systemd-units-timers.png", alt = "systemd: units and timers", hiddenInSingle = true }
+++

Sooner or later your Go or Node.js program has to run on a server: start at boot, restart after a crash, stop cleanly, run every night. On most Linux distributions {{< term "systemd" "systemd" >}} does that. This is the fifth post of the Linux series, after [/proc and observing the system](/posts/linux-proc-observability/).

> I wrote this on a Mac; nothing here ran on Linux. systemd, `systemctl` and `journalctl` do not exist on this machine, and Docker stayed off. Facts come from the freedesktop.org man pages (systemd.service, systemd.timer, systemd.exec, systemd.kill, systemd.time). What ran is marked **ran**: a Python linter, and a Go program that was only cross-compiled for Linux and never executed.

## What systemd manages

systemd is PID 1, the first process; it starts and supervises the rest. Everything is a **unit** described by a {{< term "unit-file" "unit file" >}} whose suffix gives the type: `.service`, `.timer`, `.socket`, `.target`, `.mount`, `.path`. Today we need `.service` and `.timer`.

## Anatomy of a service

This is `good/worker.service` for a small Go worker (the idea of [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/)):

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
NoNewPrivileges=yes
ProtectSystem=strict
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

- `After=` is ordering only; `Wants=` pulls the other unit in softly, `Requires=` hard.
- `Type=`: `simple` and `exec` are long-running (the docs recommend `simple` where possible and `exec` reports exec failures), `notify` waits for the service to say it is ready, `oneshot` runs and exits.
- `ExecStart=` must be an absolute path. `Restart=on-failure` restarts after an unclean exit, `RestartSec=` is the pause (default 100ms according to the docs).
- `EnvironmentFile=-path`: the dash means a missing file is not an error.
- `[Install]` only matters for `systemctl enable`: `WantedBy=multi-user.target` links the unit into boot.

## Stopping: SIGTERM, then SIGKILL

On stop, systemd sends {{< term "sigterm" "SIGTERM" >}} (or `KillSignal=`), and if processes remain after `TimeoutStopSec=` it sends {{< term "sigkill" "SIGKILL" >}}. So the worker must handle SIGTERM. My `main.go` uses `signal.NotifyContext` with `syscall.SIGTERM`, as in [Processes and signals](/posts/linux-processes-signals/), and returns, which gives {{< term "graceful-shutdown" "graceful shutdown" >}}. Set `TimeoutStopSec=` longer than your slowest batch. **Ran:** `GOOS=linux GOARCH=arm64 go vet ./...` and `go build` passed and `file` said ELF aarch64. **I never ran that binary.**

## Timers

A `.timer` activates the `.service` with the same name. From `good/worker-report.timer`:

```ini
[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=5min
```

- `OnCalendar=` is wall-clock time. systemd.time(7) lists `daily` as `*-*-* 00:00:00`, `hourly` as `*-*-* *:00:00` and `weekly` as `Mon *-*-* 00:00:00`. `systemd-analyze calendar` checks an expression; I could not run it.
- `OnBootSec=` and `OnUnitActiveSec=` are relative to boot and to the last activation.
- `Persistent=true` runs a missed job after downtime, and only affects `OnCalendar=` timers.
- `RandomizedDelaySec=` spreads load; `AccuracySec=` lets systemd coalesce wake-ups, so timers are not exact.

The service of a timer is usually `Type=oneshot`. Against {{< term "cron" "cron" >}}: timers add catch-up, dependencies, logs per unit and `systemctl list-timers`; cron is simpler, shorter to write and works on systems without systemd.

## Hardening and logs

`NoNewPrivileges=yes` blocks privilege gain, `ProtectSystem=strict` makes the filesystem read-only except allow-listed paths (`ReadWritePaths=`), `PrivateTmp=yes` gives a private `/tmp`, and `DynamicUser=yes` allocates a temporary user (it implies several of these, per systemd.exec). Output to stdout/stderr lands in the {{< term "journald" "journal" >}}: `journalctl -u worker`. After editing a unit run `systemctl daemon-reload`, then `systemctl start|stop|enable|status worker`. **I ran none of these.**

## A linter that ran

`unitlint.py` parses units (duplicate keys, `\` continuations) and checks a few rules. On the good set (**ran**):

```
good/worker-report.service: ok
good/worker-report.timer: ok
good/worker.service: ok
```

On two deliberately broken units:

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

It is a toy next to `systemd-analyze verify`, which I could not run. I skipped an OnCalendar evaluator because I could not test it against real systemd.

## A few things to watch

- `After=` does not start anything; combine it with `Wants=` or `Requires=`.
- Without a SIGTERM handler every stop ends in SIGKILL after the timeout.
- Edit a unit, then `daemon-reload`; forgetting it runs the old definition.
- Timers fire late by design (`AccuracySec=`); do not use them for exact times.
- Hardening can break a service that writes outside allowed paths; add it step by step.

## Exercise

On a Linux machine, install the example worker as a service, run `systemctl stop` and read the journal. Does it exit before the timeout? Then add a timer with `OnCalendar=minutely`, check it with `systemd-analyze calendar`, and use `list-timers`.

## What's next

The next post is “cgroups and namespaces: the base of containers”.
