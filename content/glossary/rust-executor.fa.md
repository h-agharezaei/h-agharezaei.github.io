+++
title = "Executor (Rust)"
fa_title = "Executor در Rust"
summary = "بخشی از runtime که futureها را poll می‌کند و تا وقتی waker نگفته یکی‌شان می‌تواند پیشرفت کند می‌خوابد."
category = "Rust"
related = ["rust-waker", "rust-future", "tokio"]
posts = ["rust-pin-future-internals"]
+++

کتاب‌خانه‌ی استاندارد `Future` و `Waker` را تعریف می‌کند ولی executor ندارد، پس crateای مثل Tokio آن را فراهم می‌کند. ساده‌ترین executor یک حلقه است: future را poll کن و اگر `Pending` بود thread را park کن تا waker آن را unpark کند.
