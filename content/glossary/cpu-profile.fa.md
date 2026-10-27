+++
title = "CPU profile"
summary = "نمونه‌برداری از اینکه CPU در هر لحظه کدام تابع را اجرا می‌کرد؛ برای پیدا کردن جای رفتن زمان."
category = "Node.js"
fa_title = "پروفایل CPU"
related = ["heap-snapshot", "pprof"]
posts = ["node-profiling-memory-shutdown", "linux-strace-perf"]
+++

Node.js با `node --cpu-prof` یک فایل JSON با پسوند `.cpuprofile` می‌نویسد. هر نمونه به یک call stack اشاره می‌کند و شمردن نمونه‌هایی که بالاترین فریمشان یک تابع است، زمان خودِ آن تابع را نشان می‌دهد.
