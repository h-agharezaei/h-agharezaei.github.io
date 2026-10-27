+++
title = "Dead man's switch"
summary = "An alert that fires when an expected signal does NOT arrive."
category = "Linux"
related = ["cron", "heartbeat"]
posts = ["linux-scripting-cron-safely"]
+++

A scheduled job pings a monitor after each successful run; the monitor alerts if no ping arrives within the expected window. It catches jobs that silently never started, which log-based alerts cannot see.
