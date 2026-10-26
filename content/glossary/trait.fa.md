+++
title = "Trait"
summary = "مجموعه‌ای از متدها که یک نوع می‌تواند پیاده کند؛ روش Rust برای اشتراک رفتار."
category = "Rust"
fa_title = "تریت"
related = ["ownership"]
posts = ["rust-generics-traits", "rust-trait-objects-dyn"]
+++

trait نقش interface را دارد و هم به‌عنوان قید generic (`T: Display`، static dispatch) و هم به‌شکل trait object (`dyn Display`، dynamic dispatch) استفاده می‌شود. برخلاف interfaceهای Go، یک نوع باید صریحاً `impl` آن را بنویسد.
