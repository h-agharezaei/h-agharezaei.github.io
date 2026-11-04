+++
title = "Thread (Rust)"
fa_title = "thread در Rust"
summary = "یک thread سیستم‌عامل که با std::thread::spawn شروع می‌شود؛ یک closure را هم‌زمان با thread اصلی اجرا می‌کند و حافظه‌ی برنامه را با آن‌ها شریک است."
category = "Rust"
related = ["data-race", "send-and-sync", "rust-closure"]
posts = ["rust-concurrency-threads"]
+++

`thread::spawn` یک thread سیستم‌عامل جدید شروع می‌کند و یک `JoinHandle` برمی‌گرداند. thread ممکن است از تابعی که آن را شروع کرده بیشتر عمر کند، پس closure آن باید صاحب چیزهایی باشد که به کار می‌برد (`move`). `join()` منتظرش می‌ماند و `Ok(value)` برمی‌گرداند، یا `Err` اگر thread panic کرده باشد.
