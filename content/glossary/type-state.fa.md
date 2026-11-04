+++
title = "Type-state pattern"
fa_title = "الگوی type-state"
summary = "کد کردن حالت یک شیء در type آن، تا صدا زدن متدی که در حالت فعلی مجاز نیست اصلاً کامپایل نشود."
category = "Rust"
related = ["newtype", "phantom-data", "ownership"]
posts = ["rust-typestate-patterns"]
+++

به‌جای فیلدی مثل `status: Status` که موقع اجرا بررسی‌اش می‌کنید، حالت را جزئی از type می‌کنید: `Order<Draft>` و `Order<Paid>`. برای هر حالت فقط متدهایی تعریف می‌شود که در آن حالت معنا دارند؛ پس `ship` روی `Order<Paid>` هست و روی `Order<Draft>` نیست. متدی که از یک حالت به حالت بعد می‌رود `self` را by value می‌گیرد و type جدید را برمی‌گرداند، پس حالت قبلی دیگر قابل استفاده نیست.
