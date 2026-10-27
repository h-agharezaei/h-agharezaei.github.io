+++
title = "copytruncate"
summary = "A logrotate option that copies the log and truncates the original in place instead of renaming it."
category = "Linux"
related = ["log-rotation"]
posts = ["linux-logs-journalctl"]
+++

It suits programs that cannot reopen their log file, but according to the logrotate man page a few lines written between the copy and the truncate can be lost.
