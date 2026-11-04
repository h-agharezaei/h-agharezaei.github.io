+++
title = "RefCell"
fa_title = "RefCell"
summary = "نوعی که قاعده‌های borrowing را به‌جای زمان کامپایل در زمان اجرا بررسی می‌کند، تا بتوانید مقدار را از پشت یک reference مشترک تغییر بدهید."
category = "Rust"
related = ["interior-mutability", "rc", "borrowing"]
posts = ["rust-smart-pointers"]
+++

`RefCell<T>` متدهای `borrow()` و `borrow_mut()` می‌دهد که از قاعده‌ی همیشگی پیروی می‌کنند (چند خواننده یا یک نویسنده). اگر قاعده را بشکنید در زمان اجرا panic می‌شود، یا `try_borrow_mut` یک `Err` برمی‌گرداند. برای کد تک‌threadی است.
