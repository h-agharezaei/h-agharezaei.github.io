+++
title = 'SIGPIPE'
summary = 'The signal a process gets when it writes to a pipe whose reader has closed (signal 13).'
category = 'Linux'
related = ["pipe", "signal"]
posts = ["linux-processes-signals", "py-cli-scripts"]
+++

The signal a process gets when it writes to a pipe whose reader has closed (signal 13). It is why `yes | head -1` stops: `yes` is ended by SIGPIPE and the pipeline status shows 141.
