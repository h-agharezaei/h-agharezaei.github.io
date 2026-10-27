+++
title = "Fuzzing"
fa_title = "فازینگ (fuzzing)"
summary = "دادن ورودی‌های جهش‌یافته‌ی خودکار به برنامه، با هدایت coverage، برای پیدا کردن crash و باگ."
category = "Engineering"
related = ["property-based-testing", "shrinking"]
posts = ["eng-property-based-testing", "sec-fuzzing"]
+++

fuzzer از چند ورودی اولیه شروع می‌کند، آن‌ها را جهش می‌دهد و ورودی‌هایی را نگه می‌دارد که به کد تازه می‌رسند. Go آن را داخلی دارد: `go test -fuzz FuzzName -fuzztime 5s`. به تست خاصیت‌محور نزدیک است ولی تا توقف دستی ادامه می‌دهد.
