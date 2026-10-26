+++
title = "Race condition"
summary = "باگی که نتیجه‌اش به زمان‌بندیِ همگام‌نشده‌ی دسترسی‌های هم‌زمان بستگی دارد."
category = "Go"
fa_title = "شرایط مسابقه"
related = ["mutex", "goroutine"]
posts = ["go-sync-select-context", "go-concurrency-patterns"]
+++

data race وقتی رخ می‌دهد که دو goroutine هم‌زمان به یک متغیر دسترسی داشته باشند و دست‌کم یکی بنویسد. نتیجه تعریف‌نشده است و اغلب فقط زیر بار دیده می‌شود. Go یک detector دارد: تست یا برنامه را با `go test -race` یا `go run -race` اجرا کنید.
