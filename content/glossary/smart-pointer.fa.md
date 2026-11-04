+++
title = "Smart pointer"
fa_title = "smart pointer"
summary = "نوعی که مثل یک اشاره‌گر رفتار می‌کند ولی صاحب داده‌ی مورد اشاره هم هست و وقتی از بین می‌رود کدی اجرا می‌کند، مثل Box و Rc و String."
category = "Rust"
related = ["box", "rc", "refcell", "ownership"]
posts = ["rust-smart-pointers"]
+++

smart pointer یک struct است که مثل reference رفتار می‌کند (می‌شود رویش `*` زد) ولی صاحب چیزی هم هست که به آن اشاره می‌کند و آن را با trait به اسم `Drop` تمیز می‌کند. `Box` و `Rc` و `RefCell` آن‌هایی هستند که در این بلاگ توضیح داده‌ام؛ `String` و `Vec` هم smart pointer هستند.
