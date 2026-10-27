+++
title = "systemd"
summary = "The init system and service manager on most Linux distributions, running as PID 1."
category = "Linux"
related = ["unit-file", "cron"]
posts = ["linux-systemd-units-timers", "linux-logs-journalctl"]
+++

systemd starts the other processes, supervises them, restarts them when configured to and stops them in order. Its building block is the unit, described by a unit file. It also provides `systemctl`, `journalctl` and `systemd-analyze`.
