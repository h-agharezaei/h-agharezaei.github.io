+++
title = "Borrowing"
summary = "استفاده از یک مقدار از راه reference بدون گرفتن مالکیت آن."
category = "Rust"
fa_title = "قرض‌گیری"
related = ["ownership", "lifetime"]
posts = ["rust-borrowing-references"]
+++

`&T` یک reference اشتراکی و `&mut T` یک reference انحصاری است. در هر لحظه یا چند `&T` دارید یا دقیقاً یک `&mut T`، هرگز هر دو. borrow checker این را در زمان کامپایل اعمال می‌کند و جلوی data race و باطل شدن iterator را می‌گیرد.
