+++
title = "Fan-out / fan-in"
summary = "پخش کار بین چند goroutine (fan-out) و جمع‌کردن نتیجه‌ی همه‌ی آن‌ها در یک نقطه (fan-in)."
category = "Go"
fa_title = "پخش و جمع‌آوری کار"
related = ["worker-pool", "goroutine", "channel"]
posts = ["go-concurrency-patterns"]
+++

fan-out یعنی چند goroutine از یک [channel](/fa/glossary/channel/) کار برمی‌دارند و کار بینشان تقسیم می‌شود. fan-in یعنی نتیجه‌ی همه‌ی آن‌ها به یک channel می‌ریزد که یک خواننده‌ی واحد آن را مصرف می‌کند. [worker pool](/fa/glossary/worker-pool/) نمونه‌ی رایجی است که هر دو را با هم دارد.
