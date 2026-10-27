+++
title = "Syslog severity"
fa_title = "سطح شدت syslog"
summary = "هشت سطح استاندارد لاگ از 0 (emerg) تا 7 (debug) که syslog(3) تعریف می‌کند."
category = "Linux"
related = ["journald"]
posts = ["linux-logs-journalctl"]
+++

ترتیب: emerg، alert، crit، err، warning، notice، info، debug. عدد کمتر مهم‌تر است؛ پس فیلتری مثل `journalctl -p err` یعنی اولویت 3 و هر چه شدیدتر.
