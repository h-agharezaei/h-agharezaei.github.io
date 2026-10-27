+++
title = "Syslog severity"
summary = "The eight standard log levels from 0 (emerg) to 7 (debug), defined by syslog(3)."
category = "Linux"
related = ["journald"]
posts = ["linux-logs-journalctl"]
+++

The order is emerg, alert, crit, err, warning, notice, info, debug. Lower numbers are more important, so a filter such as `journalctl -p err` means priority 3 and everything more severe.
