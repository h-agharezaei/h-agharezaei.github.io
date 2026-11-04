+++
title = "Declarative macro"
fa_title = "ماکروی declarative"
summary = "ماکرویی که با `macro_rules!` به شکل الگو و قالب نوشته می‌شود: توکن‌های فراخوانی را با الگو تطبیق می‌دهد و از روی قالب کد جدید می‌نویسد."
category = "Rust"
related = ["procedural-macro"]
posts = ["rust-macros"]
+++

`macro_rules! add { ($a:expr, $b:expr) => { $a + $b }; }` می‌گوید: وقتی دو عبارت با کاما دیدی، اولی به‌علاوه‌ی دومی را بنویس. کامپایلر پیش از چک کردن نوع‌ها هر فراخوانی را با قالب جایگزین می‌کند (به این کار expansion می‌گویند).
