+++
title = "Tokio"
fa_title = "Tokio"
summary = "پرکاربردترین crate از نوع async runtime برای Rust: futureها را اجرا می‌کند و timer، channel، قفل و I/O می‌دهد."
category = "Rust"
related = ["rust-future", "rust-async-await", "crate"]
posts = ["rust-async-tokio"]
+++

Tokio اجراکننده‌ای را فراهم می‌کند که futureها را poll می‌کند، به‌علاوه‌ی `tokio::spawn` و `join!` و `select!` و `time::sleep` و `sync::mpsc` و یک `Mutex` ناهم‌گام. `#[tokio::main]` یک runtime دور `main` می‌سازد. یک crate معمولی از crates.io است، نه بخشی از کتابخانه‌ی استاندارد.
