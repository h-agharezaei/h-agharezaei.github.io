+++
title = "start method"
summary = "روشی که multiprocessing با آن پروسه‌ی فرزند می‌سازد: spawn، fork یا forkserver."
category = 'Python'
fa_title = 'روش شروع'
related = ["process", "pickle"]
posts = ["py-multiprocessing"]
+++

start method تعیین می‌کند [پروسه](/fa/glossary/process/)ی فرزند چگونه شروع شود. با `spawn` یک interpreter تازه ماژول اصلی را دوباره import می‌کند (برای همین guard یعنی `if __name__ == '__main__':` لازم است)؛ `fork` پروسه‌ی والد را کپی می‌کند. `multiprocessing.get_start_method()` روش فعلی را نشان می‌دهد.
