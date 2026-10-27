+++
title = "Log rotation"
summary = "Renaming, compressing and deleting old log files so a log never grows without bound."
category = "Linux"
related = ["journald", "structured-logging"]
posts = ["linux-logs-journalctl"]
+++

On Linux, `logrotate` does this from a config file: how often or at what size to rotate and how many old files to keep (`rotate N`). A program still holding the old file open needs a signal or `copytruncate`.
