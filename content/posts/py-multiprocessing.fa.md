+++
date = '2027-04-07T10:00:00+03:30'
draft = false
title = 'multiprocessing در Python'
description = 'multiprocessing در Python روی macOS: spawn و guard، Pool و ProcessPoolExecutor، محدودیت pickle، Value و Manager، حافظه‌ی مشترک و خطاها.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "multiprocessing", "concurrency", "processes", "pickle"]
cover = { image = "/images/covers/py-multiprocessing.fa.png", alt = "multiprocessing در Python", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-gil-threading/) دیدیم GIL به thread‌ها اجازه می‌دهد برای انتظار کمک کنند، نه برای محاسبه. جواب استاندارد برای کار CPU، {{< term "process" "پروسه" >}} است: هر کدام interpreter و GIL خودش را دارد. این مقاله ماژول `multiprocessing` را روی macOS اجرا می‌کند و نشان می‌دهد کجا گیر می‌دهد. اگر Go بلدید ([شروع با Go](/fa/posts/go-getting-started/))، انتظار تشریفات بیشتری از `go f()` داشته باشید.

> Python 3.14.0 روی macOS، دموها در یک پوشه‌ی محلی. ماشین شلوغ بود (load average بالای ۶)، پس **هیچ عدد سرعتی** منتشر نمی‌کنم، فقط تعداد و بایت. چیزی روی Linux اجرا نکردم.

## start method و guard اصلی

```text
start method: spawn
```

این خروجی `multiprocessing.get_start_method()` اینجاست. روی macOS {{< term "start-method" "start method" >}} برابر `spawn` است: فرزند یک interpreter تازه است که ماژول اصلی شما را دوباره import می‌کند. طبق مستندات (اجرا نکرده‌ام)، Linux قبلاً `fork` بود و در ۳.۱۴ پیش‌فرضش به `forkserver` عوض شد.

پس بدون `if __name__ == '__main__':` فرزند همان کدی را که فرزند می‌سازد دوباره اجرا می‌کند. اسکریپتی را که در سطح بالا یک `Process` شروع می‌کند با timeout ۱۵ ثانیه (یک subprocess با `timeout=15`) آزمایش کردم. Python جلویش را گرفت:

```text
RuntimeError:
        An attempt has been made to start a new process before the
        current process has finished its bootstrapping phase.
```

به‌جای حلقه خطا می‌دهد، اما همیشه guard را بنویسید.

## Process، Pool و executor

```python
if __name__ == '__main__':
    with mp.Pool(4) as pool:
        print(pool.map(square, range(10)))
    with ProcessPoolExecutor(max_workers=3) as ex:
        print(list(ex.map(square, range(5))))
```

```text
Pool.map: [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
Executor.map: [0, 1, 4, 9, 16]
```

`mp.Process(target=..., args=...)` ساده با `start()` و `join()` هم کار کرد (کد خروج فرزند ۰). برای ۲۰۰ کار، مجموعه‌ی pid کارگرها حداکثر ۴ عضو داشت و والد در آن نبود: پروسه‌های واقعاً جدا. این یک {{< term "worker-pool" "worker pool" >}} است، مثل نسخه‌ی thread در مقاله‌ی قبل؛ `ProcessPoolExecutor` همان API مربوط به `ThreadPoolExecutor` را دارد و عوض‌کردنشان یک خط است.

## همه‌چیز pickle می‌شود

آرگومان‌ها و نتیجه‌ها با {{< term "pickle" "pickle" >}} بین پروسه‌ها می‌روند:

```text
pickled bytes for 1,000,000 ints: 4871352
pickled bytes for one int: 5
PicklingError Can't pickle <function <lambda> at 0x1076ff110>: it's not found as __main__.<lambda>
```

دو نتیجه. lambda (یا تابع محلی) فرستاده نمی‌شود؛ `def` سطح بالا بنویسید. و لیست یک میلیون عدد حدود ۴٫۹ مگابایت در هر جهت است؛ فرستادن کارهای کوچک با داده‌ی بزرگ می‌تواند بیشتر از صرفه‌ی محاسبه هزینه داشته باشد (به‌جایش شناسه یا مسیر فایل بدهید). این هزینه را اندازه نگرفتم.

## اشتراک state

پروسه‌ها متغیر مشترک ندارند. چهار پروسه هرکدام ۲۰٬۰۰۰ بار ۱ به یک `Value` مشترک اضافه کردند:

```text
Value no lock  : 61798 expected 80000
Value with lock: 80000 expected 80000
```

همان {{< term "race-condition" "race condition" >}} thread‌ها، با همان درمان: `with v.get_lock():` (یک {{< term "mutex" "mutex" >}}). عدد بدون قفل در هر اجرا فرق می‌کند، عدد با قفل نه. ابزارهای دیگری که اجرا کردم:

```text
Array: [0.0, 2.5, 0.0]
Manager dict   : 8000 expected 8000
SharedMemory   : b'hello'
after unlink: FileNotFoundError (no leak)
```

`mp.Array` آرایه‌ی تایپ‌دار با اندازه‌ی ثابت است. `Manager` یک پروسه‌ی سرور دارد که `dict` یا `Lock` را نگه می‌دارد و دیگران با proxy به آن می‌رسند: منعطف اما کندتر، و برای ۸٬۰۰۰ افزایش قفل گذاشتم. {{< term "shared-memory" "SharedMemory" >}} بلوک خام است: فرزند با نام وصل شد و `hello` نوشت، والد خواند، سپس `close()` و `unlink()`؛ وصل‌شدن دوباره `FileNotFoundError` داد، پس چیزی نشت نکرد. برای فرستادن پیام، `mp.Queue` کار کرد: چهار فرزند هرکدام `(n, n*n)` گذاشتند و والد `[(0, 0), (1, 1), (2, 4), (3, 9)]` گرفت.

## initializer و خطاها

`Pool(2, initializer=init, initargs=('cfg',))` تابع `init` را یک بار برای هر کارگر اجرا می‌کند؛ جای مناسب برای راه‌اندازی مثل باز کردن اتصال. `tagged` خروجی `['cfg:0', 'cfg:1', 'cfg:2']` داد.

وقتی کارگر exception می‌دهد، در والد دوباره raise می‌شود و traceback کارگر به‌عنوان علتش ضمیمه است:

```text
multiprocessing.pool.RemoteTraceback:
...
  File ".../errors.py", line 9, in boom
    raise ValueError('bad input 2')
ValueError: bad input 2

The above exception was the direct cause of the following exception:
...
ValueError: bad input 2
```

executor هم `bad input 2` را به همین شکل raise کرد.

## thread، goroutine، worker_threads

thread‌ها حافظه را به اشتراک می‌گذارند اما یک GIL دارند؛ پروسه‌ها Python خالص را موازی می‌کنند اما هزینه‌ی شروع و pickle دارند. goroutine ارزان است و حافظه را به اشتراک می‌گذارد ([goroutine و channel](/fa/posts/go-goroutines-channels/)). `worker_threads` در Node تردهای جدا با event loop خودشان‌اند ([worker threads و cluster](/fa/posts/node-worker-threads-cluster/)); پروسه‌ی Python به یک interpreter کامل جدید نزدیک‌تر است.

## چند نکته‌ی مهم

- همیشه guard یعنی `if __name__ == '__main__':` را بنویسید؛ start method پیش‌فرض در هر سیستم‌عامل فرق دارد.
- تابع و آرگومان‌ها باید قابل pickle باشند؛ کارها را درشت نگه دارید.
- state تغییرپذیر مشترک قفل می‌خواهد؛ بهتر است نتیجه را برگردانید.
- حافظه‌ی مشترک را آزاد کنید: `close()` در همه، `unlink()` یک بار.
- برای کار CPU از پروسه استفاده کنید؛ برای انتظار، thread یا asyncio ارزان‌تر است.

## تمرین

شمارنده‌ی اعداد اول روی بازه‌ی ۰ تا ۲٬۰۰۰٬۰۰۰ بنویسید که به ۸ تکه تقسیم شود. یک بار با `Pool.map` و یک بار با `ProcessPoolExecutor` اجرایش کنید. pid کارگرها را چاپ کنید تا ثابت شود بیش از یک پروسه کار کرده، و فقط وقتی `uptime` ماشین آرام را نشان می‌دهد زمانش را بگیرید.

## قدم بعدی

مقاله‌ی بعد «asyncio در Python» است، راه تک‌thread برای مدیریت هزاران کار منتظر.
