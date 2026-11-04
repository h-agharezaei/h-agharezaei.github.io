+++
title = "Raw pointer"
fa_title = "Raw pointer در Rust"
summary = "آدرسی خالی (`*const T` یا `*mut T`) بدون lifetime و بدون قانون borrow؛ ساختنش امن است ولی deref کردنش `unsafe` می‌خواهد."
category = "Rust"
related = ["rust-ffi", "undefined-behavior"]
posts = ["rust-unsafe-ffi"]
+++

`&raw const x` یک `*const i32` می‌سازد که به `x` اشاره می‌کند. کامپایلر چک نمی‌کند آدرس معتبر، هم‌تراز یا غیر null باشد، پس خواندن از طریق `*p` چیزی است که شما قول می‌دهید درست باشد. raw pointer در مرز با C و داخل abstractionهای امن مثل `split_at_mut` به کار می‌رود.
