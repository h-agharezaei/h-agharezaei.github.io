+++
title = "Interior mutability"
fa_title = "interior mutability"
summary = "تغییر یک مقدار از پشت reference مشترک، با جابه‌جایی بررسی borrowing از زمان کامپایل به زمان اجرا."
category = "Rust"
related = ["refcell", "borrowing"]
posts = ["rust-smart-pointers"]
+++

معمولاً reference مشترک (`&T`) یعنی فقط خواندن. نوع‌هایی مثل `RefCell` و `Mutex` اجازه می‌دهند از پشت `&T` تغییر بدهید، به این شرط که خودشان قاعده‌ها را هنگام اجرای برنامه بررسی کنند. کامپایلر نمی‌تواند این را از قبل ثابت کند، پس بررسی به عهده‌ی خود نوع است.
