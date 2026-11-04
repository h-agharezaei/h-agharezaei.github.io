+++
title = "Trait object"
fa_title = "Trait object در Rust"
summary = "مقداری که از طریق `dyn Trait` استفاده می‌شود: نوع واقعی‌اش فراموش شده و فقط متدهای trait معلوم است و در زمان اجرا پیدا می‌شود."
category = "Rust"
related = ["trait", "vtable", "box"]
posts = ["rust-trait-objects-dyn"]
+++

`Box<dyn Shape>` اشاره‌گری به مقداری است که `Shape` را پیاده کرده؛ بدون اینکه بدانید `Square` است یا `Circle` می‌توانید متدهای `Shape` را رویش صدا بزنید. به این ترتیب یک `Vec` می‌تواند نوع‌های مختلف را نگه دارد، به بهای یک جست‌وجو در [vtable](/fa/glossary/vtable/) در هر فراخوانی. هر trait‌ای را نمی‌شود این‌طور به کار برد (باید با dyn سازگار باشد).
