+++
title = "Worker pool"
summary = "تعداد ثابتی goroutine که کارها را از یک صف مشترک برمی‌دارند."
category = "Go"
fa_title = "استخر کارگر"
related = ["goroutine", "channel", "errgroup"]
posts = ["go-concurrency-patterns", "go-graceful-shutdown-workers", "node-worker-threads-cluster", "py-gil-threading", "py-multiprocessing"]
+++

به‌جای ساختن یک goroutine برای هر کار، N کارگر بالا می‌آورید که از یک [channel](/fa/glossary/channel/) کارها می‌خوانند. این کار مصرف حافظه و فشار روی سرویس پایین‌دست را محدود می‌کند. تولیدکننده بعد از اتمام channel را می‌بندد و کارگرها با پایان `range` خارج می‌شوند.
