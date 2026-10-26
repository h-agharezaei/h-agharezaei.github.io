+++
title = "Hash table"
fa_title = "جدول هش"
summary = "ساختاری که کلید را با محاسبه‌ی hash پیدا می‌کند و جست‌وجو را به‌طور میانگین O(1) می‌کند. map در Go یکی از آن‌هاست."
category = "Algorithms"
related = ["big-o"]
posts = ["algo-big-o-measured"]
+++

کلید hash می‌شود تا یک bucket انتخاب شود، پس جست‌وجو همه‌ی عنصرها را نمی‌گردد. هزینه‌اش یک مرحله‌ی ثابت hash در هر دسترسی است و برای همین یک slice خیلی کوچک می‌تواند از map سریع‌تر باشد. نگاه کنید به [Big-O](/fa/glossary/big-o/).
