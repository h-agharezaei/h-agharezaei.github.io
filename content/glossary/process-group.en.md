+++
title = 'Process group'
summary = 'A set of related processes (for example a pipeline) that can receive a signal together.'
category = 'Linux'
related = ["process", "signal"]
posts = ["linux-processes-signals"]
+++

A set of related processes (for example a pipeline) that can receive a signal together. Send a signal to the whole group with `kill -- -PGID`. A new session (`setsid`) starts a new group.
