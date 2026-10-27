+++
title = "pickle"
summary = "تبدیل شیء Python به بایت و برعکس؛ multiprocessing با آن داده را بین پروسه‌ها می‌فرستد."
category = 'Python'
fa_title = 'pickle'
related = ["process"]
posts = ["py-multiprocessing"]
+++

`pickle` یک شیء Python را به بایت و دوباره به شیء تبدیل می‌کند. `multiprocessing` هر آرگومان و نتیجه‌ای را که به [پروسه](/fa/glossary/process/)ی دیگر می‌فرستد pickle می‌کند؛ پس باید قابل pickle باشد (lambda نیست) و داده‌ی بزرگ هم زمان و بایت خرج می‌کند.
