+++
title = "Reentrancy"
summary = "یک فراخوانی بیرونی به طرف مقابل اجازه می‌دهد پیش از آن‌که قرارداد state خودش را کامل به‌روز کند، دوباره آن را صدا بزند."
category = "Blockchain"
fa_title = "بازگشت دوباره به قرارداد (reentrancy)"
related = ["checks-effects-interactions", "smart-contract", "erc-721"]
posts = ["bc-contract-security"]
+++

نمونه‌ی کلاسیک: صندوقی که قبل از صفر کردن موجودی ETH می‌فرستد و `receive()` گیرنده دوباره `withdraw()` را صدا می‌زند. گونه‌های دیگر: بین‌تابعی (ورود از تابع دیگر) و فقط‌خواندنی (قرارداد دیگری `view` نیمه‌کاره را می‌خواند). رفعش [checks-effects-interactions](/fa/glossary/checks-effects-interactions/) به‌اضافه‌ی یک قفل است.
