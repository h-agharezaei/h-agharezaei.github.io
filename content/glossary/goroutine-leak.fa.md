+++
title = "Goroutine leak"
summary = "goroutineای که برای همیشه گیر کرده (معمولاً روی یک channel) و هیچ‌وقت حافظه‌اش را آزاد نمی‌کند."
category = "Go"
fa_title = "نشت goroutine"
related = ["goroutine", "channel", "context"]
posts = ["go-concurrency-patterns"]
+++

goroutineای که منتظر channelی است که هیچ‌کس هرگز از آن نمی‌خواند یا در آن نمی‌نویسد، تا پایان برنامه زنده می‌ماند. اگر کد نشت‌دار را بارها صدا بزنید، هر فراخوانی یک goroutine گیرکرده اضافه می‌کند و `runtime.NumGoroutine()` مدام بالا می‌رود. راه‌حل معمول یک channel بافردار برای آخرین نتیجه و یک [context](/fa/glossary/context/) است که به کار می‌گوید متوقف شود.
