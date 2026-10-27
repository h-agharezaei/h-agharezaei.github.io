+++
title = 'SIGKILL'
summary = 'The forced kill (signal 9); it cannot be caught or ignored, so no cleanup code runs.'
category = 'Linux'
related = ["signal", "sigterm"]
posts = ["linux-processes-signals", "linux-systemd-units-timers", "linux-memory-page-cache-oom"]
+++

The forced kill (signal 9); it cannot be caught or ignored, so no cleanup code runs. Use it only after SIGTERM failed. A shell reports exit status 137 (128+9).
