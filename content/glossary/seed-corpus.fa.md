+++
title = "Seed corpus"
fa_title = "corpus اولیه"
summary = "ورودی‌های شروع که به fuzzer داده می‌شود، بهتر است نمونه‌های واقعی باشند."
category = "Security"
related = ["fuzzing", "regression"]
posts = ["sec-fuzzing"]
+++

corpus اولیه مجموعه‌ی کوچکی از ورودی‌های معتبر است (در Go با `f.Add` و فایل‌های `testdata/fuzz`). fuzzer آن‌ها را جهش می‌دهد، پس seedهای خوب سریع به کد عمیق می‌رسند. ورودی‌های شکست‌خورده همان‌جا ذخیره و با `go test` ساده دوباره اجرا می‌شوند.
