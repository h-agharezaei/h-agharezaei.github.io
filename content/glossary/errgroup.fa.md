+++
title = "errgroup"
summary = "ابزاری از `golang.org/x/sync` که چند goroutine را با هم اجرا می‌کند و با اولین خطا بقیه را لغو می‌کند."
category = "Go"
fa_title = "ارورگروپ"
related = ["context", "worker-pool"]
posts = ["go-concurrency-patterns"]
+++

`errgroup.WithContext` یک group و یک [context](/fa/glossary/context/) مشتق‌شده برمی‌گرداند. `g.Go(fn)` یک goroutine شروع می‌کند؛ `g.Wait()` تا پایان همه بلاک می‌کند و اولین خطای غیر nil را برمی‌گرداند. `g.SetLimit(n)` هم هم‌زمانی را محدود می‌کند، بدون اینکه [worker pool](/fa/glossary/worker-pool/) دستی بنویسید.
