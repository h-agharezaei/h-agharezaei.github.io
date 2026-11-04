+++
title = "PhantomData"
fa_title = "PhantomData"
summary = "نشانه‌ای با اندازه‌ی صفر که به struct اجازه می‌دهد پارامتر typeای داشته باشد که واقعاً ذخیره‌اش نمی‌کند؛ پایه‌ی نشانه‌های type-state."
category = "Rust"
related = ["type-state"]
posts = ["rust-typestate-patterns"]
+++

Rust اجازه نمی‌دهد struct پارامتر type به نام `S` اعلام کند و هرگز از آن استفاده نکند. `PhantomData<S>` فیلدی است که برای کامپایلر از `S` «استفاده» می‌کند ولی جایی اشغال نمی‌کند: `size_of::<PhantomData<T>>()` برابر ۰ است. با آن، type‌ای مثل `Order<S>` می‌تواند حالت `S` را فقط در type با خود داشته باشد، بی‌آنکه چیزی در حافظه ذخیره شود.
