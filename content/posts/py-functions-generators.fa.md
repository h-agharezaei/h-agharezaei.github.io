+++
date = '2027-01-28T10:00:00+03:30'
draft = false
title = 'توابع، closure و generator در Python'
description = 'توابع، closure، decorator و generator در Python برای برنامه‌نویس‌های Go و Node.js: انواع پارامتر، late binding، yield، itertools و lru_cache روی 3.14.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "beginner", "functions", "closures", "generators"]
cover = { image = "/images/covers/py-functions-generators.fa.png", alt = "توابع، closure و generator در Python", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-types-control-flow/) نوع‌ها و کنترل جریان را دیدیم. توابع جایی هستند که Python با Go حس متفاوتی پیدا می‌کند: تابع‌ها شیء معمولی‌اند، با {{< term "decorator" "decorator" >}} پوشانده می‌شوند و یک تابع می‌تواند وسط کار بایستد و بعداً ادامه بدهد. مقایسه با [توابع در Go](/fa/posts/go-functions-defer-errors/) را فقط جایی آورده‌ام که مطمئنم، و [event loop در Node.js](/fa/posts/node-event-loop/) پیش‌زمینه‌ی خوبی برای بخش closure است.

> همه‌چیز با Python 3.14.0 روی macOS اجرا شده است. فایل‌های دمو اسکریپت‌های محلی `params.py`، `closures.py` و `gens.py` هستند.

## پارامترها

`/` پارامترهای فقط-موقعیتی (positional-only) را تمام می‌کند و `*` پارامترهای فقط-کلیدی (keyword-only) را شروع می‌کند:

```python
def f(a, b, /, c, *, d=0):
    return (a, b, c, d)
```

```text
f(1, 2, 3, d=4)  -> (1, 2, 3, 4)
f(a=1, b=2, c=3) -> TypeError: f() got some positional-only arguments passed as keyword arguments: 'a, b'
f(1, 2, 3, 4)    -> TypeError: f() takes 3 positional arguments but 4 were given
```

مقدار پیش‌فرض یک بار و هنگام اجرای `def` محاسبه می‌شود، و همین باگ کلاسیک را می‌سازد:

```python
def add_item(x, bucket=[]):
    bucket.append(x)
    return bucket
```

```text
[1, 2, 3] [1, 2, 3] [1, 2, 3]
```

هر سه فراخوانی یک لیست را برگرداندند (چاپ بعد از همه‌ی فراخوانی‌ها انجام می‌شود، پس وضعیت نهایی را سه بار می‌بینید). راه‌حل: `bucket=None` و `if bucket is None: bucket = []`؛ آن‌وقت دو فراخوانی `[1] [2]` چاپ کردند.

`*args` پارامترهای موقعیتی اضافه را در یک tuple و `**kwargs` کلیدی‌ها را در یک dict جمع می‌کند. `show(1, 2, x=3)` خروجی `(1, 2) {'x': 3}` داد و `show(*[1, 2], **{"y": 4})` سمت فراخوانی باز می‌کند.

## Closure

تابع‌ها مقدارند و تابع داخلی متغیرهایی را که استفاده می‌کند نگه می‌دارد. به این می‌گویند {{< term "closure" "closure" >}}. برای مقداردهی دوباره‌ی متغیر بیرونی (نه فقط تغییر دادنش) به `nonlocal` نیاز دارید:

```python
def make_counter():
    count = 0
    def inc():
        nonlocal count
        count += 1
        return count
    return inc
```

دو شمارنده مستقل‌اند: `c1(), c1(), c2()` خروجی `1 2 1` داد. بدون `nonlocal`، عبارت `n += 1` خطای `UnboundLocalError: cannot access local variable 'n' where it is not associated with a value` داد.

گیر اصلی {{< term "late-binding" "late binding" >}} است: closure متغیر را موقع اجرا جست‌وجو می‌کند.

```python
fs = [lambda: i for i in range(3)]
print([f() for f in fs])          # [2, 2, 2]
fs = [lambda i=i: i for i in range(3)]
print([f() for f in fs])          # [0, 1, 2]
```

همه‌ی lambdaها `i` نهایی را دیدند. آرگومان پیش‌فرض (`i=i`) مقدار را ثابت می‌کند؛ `functools.partial` هم `[0, 1, 2]` چاپ کرد.

## Decorator

decorator تابعی است که تابعی را می‌گیرد و جایگزینش را برمی‌گرداند. `@timed` من به‌جای اندازه‌گیری زمان، تعداد فراخوانی‌ها را می‌شمارد:

```python
def timed(fn):
    def wrapper(*a, **k):
        wrapper.calls += 1
        return fn(*a, **k)
    wrapper.calls = 0
    return wrapper
```

بدون `functools.wraps` تابع تزئین‌شده هویتش را از دست داد. همان تابع را یک بار بدون و یک بار با `@functools.wraps(fn)` اجرا کردم:

```text
wrapper None 2
hello2 say hello 3
```

خط اول `__name__`، `__doc__` و `calls` بدون `wraps` است. decorator با آرگومان یک لایه‌ی بیشتر دارد. این `@retry(times=3)` تابعی را می‌پوشاند که دو بار (به‌صورت قطعی) شکست می‌خورد:

```text
  attempt 1 failed: boom #1
  attempt 2 failed: boom #2
ok after 3 calls
```

با `times=2` و تابعی که همیشه شکست می‌خورد، دو تلاش چاپ شد و بعد `gave up: down`: تلاش آخر خطا را دوباره بالا می‌اندازد.

## Generator

تابعی که `yield` دارد یک generator برمی‌گرداند و تا نخواهید چیزی اجرا نمی‌کند. چاپ‌ها این را ثابت می‌کنند:

```text
created, nothing printed yet
start
yield 1
1
yield 2
2
end
StopIteration
```

این همان {{< term "lazy-evaluation" "ارزیابی تنبل" >}} است. تفاوت حافظه قطعی است: `sys.getsizeof` برای `list(range(1_000_000))` برابر 8000056 بایت است و برای generator expression یعنی `(x for x in range(1_000_000))` برابر 200 بایت (اندازه‌ی خود شیء generator، نه مقدارهای آینده‌اش). نکته‌ی دیگر: generator یک‌بار مصرف است؛ `sum` اول `499999500000` داد و دومی `0`.

`yield from` کار را به generator دیگر می‌سپارد: `list(outer())` خروجی `[0, 1, 2, 3]` داد. generator می‌تواند با `send()` هم مقدار بگیرد؛ در همین یک جمله بگذریم.

## پروتکل iterator

`for` اول `iter()` و بعد پشت‌سرهم `__next__()` را صدا می‌زند تا `StopIteration` بیاید. یک {{< term "iterator" "iterator" >}} دست‌نویس:

```python
class Countdown:
    def __init__(self, n): self.n = n
    def __iter__(self): return self
    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1
```

`list(Countdown(3))` خروجی `[3, 2, 1]` داد. generator فقط راه کوتاه نوشتن همین است.

## itertools و lru_cache

```text
list(islice(naturals(), 5))      [0, 1, 2, 3, 4]
list(chain([1, 2], "ab", (9,)))  [1, 2, 'a', 'b', 9]
```

`islice` یک generator بی‌پایان را می‌برد. `groupby` فقط آیتم‌های *مجاور* را گروه می‌کند. روی `["apple", "avocado", "banana", "blueberry", "apricot"]` بر اساس حرف اول، سه گروه چاپ شد که `a` دو بار آمد؛ روی لیست مرتب‌شده دو گروه.

{{< term "memoization" "Memoization" >}} با `@functools.lru_cache` آماده است. برای `fib(30)` بازگشتی، `cache_info()` این را چاپ کرد: `CacheInfo(hits=28, misses=31, maxsize=None, currsize=31)`؛ یعنی 31 ورودی متمایز که هرکدام یک بار محاسبه شدند.

## مقایسه با Go

Go هم closure دارد و متغیرها را با reference می‌گیرد. معنای متغیر حلقه در Go را اینجا آزمایش نکردم. Go generator از نوع `yield` ندارد؛ برنامه‌ی کوچکی با `iter.Seq[int]` در Go 1.26 اجرا کردم، تابعی که callback به شکل `yield func(int) bool` می‌گیرد، و `for v := range Count(3)` مقدارهای `1 2 3` را چاپ کرد. این مدل push است، برخلاف `next()` در Python که pull است.

## چند نکته‌ی مهم

- هیچ‌وقت آرگومان پیش‌فرض mutable نگذارید؛ از `None` استفاده کنید.
- closure متغیر را می‌گیرد، نه مقدار را: حلقه‌ها را با `i=i` درست کنید.
- در decorator همیشه `functools.wraps` بگذارید.
- `groupby` ورودی مرتب می‌خواهد و generator را فقط یک بار می‌شود مصرف کرد.
- آرگومان‌های `lru_cache` باید hashable باشند.

## تمرین

1. `@count_calls` بنویسید که `.calls` را در دسترس بگذارد، بعد `@retry` را روی آن بگذارید.
2. generator به نام `chunks(iterable, n)` با `islice` بنویسید.
3. گیر `groupby` را بازتولید کنید و به دو روش درستش کنید.

## قدم بعدی

مقاله‌ی بعدی «کلاس و dataclass در Python» است.
