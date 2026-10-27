+++
title = 'Load average'
summary = 'Average number of runnable jobs (on Linux also those waiting for disk) over the last 1, 5 and 15 minutes.'
category = 'Linux'
related = ["process"]
posts = ["linux-proc-observability"]
+++

The three numbers `uptime` prints: the average count of jobs ready to run over 1, 5 and 15 minutes. Compare it with the number of cores; the exact definition is not identical on Linux and macOS.
