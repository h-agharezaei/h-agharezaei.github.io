+++
title = "journald"
summary = "The systemd service that collects logs from services and the kernel into a structured journal."
category = "Linux"
related = ["systemd"]
posts = ["linux-systemd-units-timers", "linux-logs-journalctl"]
+++

You read the journal with `journalctl`, for example `journalctl -u myservice` for one unit. A service only has to write to stdout or stderr; the journal captures it.
