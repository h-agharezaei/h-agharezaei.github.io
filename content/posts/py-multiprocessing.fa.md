+++
date = '2027-04-07T10:00:00+03:30'
draft = false
title = 'multiprocessing در Python'
description = 'multiprocessing در Python روی macOS: spawn و guard، Pool و ProcessPoolExecutor، محدودیت pickle، Value و Manager، حافظه‌ی مشترک و خطاها.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "multiprocessing", "concurrency", "processes", "pickle"]
cover = { image = "/images/covers/py-multiprocessing.fa.png", alt = "multiprocessing در Python", hiddenInSingle = true }
+++

خط لوله‌ای دارید که باید کوهی از کار CPU را هضم کند: هش یک میلیون فایل، تغییر اندازه‌ی تصویرها، شمردن عددهای اول در بازه‌های بزرگ. می‌خواهید از همه‌ی هسته‌های ماشین استفاده کند. [GIL](/fa/posts/py-gil-threading/) می‌گوید در Python استاندارد threadها نمی‌توانند این کار را بکنند، چون نوبتی کار می‌کنند. جواب استاندارد این است که به‌جایشان از {{< term "process" "processها" >}} استفاده کنید.

process یک برنامه‌ی کامل در حال اجرا با حافظه‌ی خودش است. اگر چهار process راه بیندازید چهار مفسر Python جدا دارید و هر کدام GIL خودش را دارد، پس هر چهار واقعاً هم‌زمان روی چهار هسته اجرا می‌شوند. تصویری که من در ذهن دارم: thread مثل چند آشپز است که یک آشپزخانه و یک اجاق مشترک دارند؛ process مثل چند آشپزخانه است. اجاق بیشتر داریم، ولی حالا آشپزخانه‌ها نمی‌توانند دستشان را داخل یخچال هم بکنند. هر چیزی که باید رد و بدل شود باید بسته‌بندی و حمل شود. همین بسته‌بندی هزینه‌ی این روش است و بیشتر این پست درباره‌ی جاهایی است که خودش را نشان می‌دهد.

این پست ماژول `multiprocessing` را روی macOS اجرا می‌کند. اگر Go ([شروع کار با Go](/fa/posts/go-getting-started/)) را می‌شناسید، انتظار تشریفات بیشتری نسبت به `go f()` داشته باشید.

> همه‌ی دموها را دوباره با Python 3.14.0 روی macOS اجرا کردم؛ اسکریپت‌های محلی هستند. ماشین شلوغ بود (میانگین بار یک‌دقیقه‌ای هنگام اجرای دوباره بین ۱۱ و ۱۴ بود)، برای همین **هیچ عدد سرعتی** منتشر نمی‌کنم، فقط شمارش‌ها، بایت‌ها و خروجی‌ها. چیزی را روی Linux اجرا نکردم. بعد از اجراها با `ps` بررسی کردم که هیچ‌کدام از processهای workerِ من باقی نمانده باشد.

## start method و محافظ main

یک process جدید چطور ساخته می‌شود؟ ماژول تنظیمی دارد به نام {{< term "start-method" "start method" >}}. روی این Mac چاپ کرد:

```text
start method: spawn
```

با `spawn` فرزند یک مفسر کاملاً تازه است. برای اینکه بداند چه کدی را اجرا کند، ماژول اصلی شما را دوباره از بالا import می‌کند. طبق مستندات Python (این را روی Linux اجرا نکردم)، Linux تا قبل از 3.14 از `fork` استفاده می‌کرد، یعنی کپی‌کردن process والد، و پیش‌فرضش را در Python 3.14 به `forkserver` تغییر داد. پس یک اسکریپت یکسان روی سیستم‌های مختلف می‌تواند رفتار متفاوتی داشته باشد.

این import دوباره پیامد دارد. اگر اسکریپت شما در سطح بالای فایل یک فرزند راه بیندازد، فرزند اسکریپت را import می‌کند، آن یک فرزند دیگر راه می‌اندازد و همین‌طور ادامه. برای جلوگیری، هر چیزی که process راه می‌اندازد باید زیر محافظ `if __name__ == '__main__':` باشد که در نسخه‌ی دوباره import شده نادرست است. اسکریپتی بدون محافظ را آزمایش کردم که در سطح بالا یک `Process` راه می‌اندازد، زیر timeout پانزده‌ثانیه‌ای. Python آن را با این خطا متوقف کرد:

```text
RuntimeError:
        An attempt has been made to start a new process before the
        current process has finished its bootstrapping phase.
```

(پیام کامل با یک راهنمای بلند درباره‌ی `freeze_support()` ادامه دارد.) پس Python به‌جای حلقه‌ی بی‌پایان، امتناع می‌کند. باز هم همیشه محافظ را بنویسید.

## Process، Pool و executor

پایین‌ترین ابزار `mp.Process(target=..., args=...)` با `start()` و `join()` است. در دموی `basics.py` یک فرزند `hello from child` چاپ کرد و `exitcode` آن `0` بود. بیشتر وقت‌ها نمی‌خواهید processها را یکی‌یکی مدیریت کنید، پس از pool استفاده می‌کنید: مجموعه‌ی ثابتی از processهای worker که از یک فهرست کار برمی‌دارند:

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

`pool.map` فهرست را بین چهار worker تقسیم می‌کند و نتیجه‌ها را به ترتیب اصلی برمی‌گرداند. برای اثبات اینکه processهای واقعی و جدا بودند، دمو از ۲۰۰ کار شناسه‌ی process (`os.getpid()`) را پرسید و مجموعه‌ی شناسه‌ها را جمع کرد: حداکثر ۴ عضو داشت و شناسه‌ی والد در آن نبود. این یک {{< term "worker-pool" "worker pool" >}} است، مثل نسخه‌ی thread در پست قبل. `ProcessPoolExecutor` همان API مربوط به `ThreadPoolExecutor` را دارد، پس رفتن از thread به process می‌تواند یک تغییر یک‌خطی باشد.

## همه‌چیز pickle می‌شود

processها حافظه‌ی مشترک ندارند، پس آرگومان‌ها و نتیجه‌ها باید به بایت تبدیل شوند، از یک pipe رد شوند و آن طرف دوباره ساخته شوند. Python این کار را با {{< term "pickle" "pickle" >}} انجام می‌دهد. دموی `pickling.py` معنایش را در عمل نشان می‌دهد:

```text
pickled bytes for 1,000,000 ints: 4871352
pickled bytes for one int: 5
PicklingError Can't pickle <function <lambda> at 0x1076ff110>: it's not found as __main__.<lambda>
```

(آدرس در خط آخر هر بار عوض می‌شود.) دو پیامد دارد:

- lambda یا تابعی که داخل تابع دیگر تعریف شده را نمی‌شود فرستاد. pickle توابع را با اسم می‌فرستد و این‌ها اسمی ندارند که import شود. از یک `def` سطح بالا استفاده کنید.
- فهرستی از یک میلیون عدد صحیح حدود ۴٫۹ مگابایت است و باید تا worker برود و برگردد. اگر هر کار کوچک و داده‌اش بزرگ باشد، فرستادن داده می‌تواند بیشتر از صرفه‌جویی محاسبه خرج بردارد. شناسه یا مسیر فایل بدهید و بگذارید worker خودش داده را بخواند. این هزینه را اندازه نگرفتم.

## به اشتراک گذاشتن state

چون processها متغیر مشترک ندارند، چطور روی یک عدد کار می‌کنند؟ دمو چهار process دارد که هر کدام ۲۰٬۰۰۰ بار به یک `Value` مشترک یکی اضافه می‌کنند، اول بدون قفل و بعد با قفل:

```text
Value no lock  : 61798 expected 80000
Value with lock: 80000 expected 80000
```

همان {{< term "race-condition" "race condition" >}} threadها است با همان راه‌حل: `with v.get_lock():` که یک {{< term "mutex" "mutex" >}} است. عدد بدون قفل هر بار فرق می‌کند: خط بالا از اجرای اصلی است و در اجرای دوباره‌ی من `20439` چاپ شد. عدد با قفل همیشه ۸۰۰۰۰ است. دمو سه راه دیگر برای به اشتراک گذاشتن یا فرستادن داده دارد:

```text
Array: [0.0, 2.5, 0.0]
Manager dict   : 8000 expected 8000
SharedMemory   : b'hello'
after unlink: FileNotFoundError (no leak)
```

- `mp.Array` آرایه‌ی ثابت‌اندازه‌ای از یک نوع است (اینجا double)؛ عضو وسط را ۲٫۵ گذاشتم.
- `Manager` یک process سرور راه می‌اندازد که یک `dict` یا `Lock` را نگه می‌دارد و بقیه از طریق شیءهای proxy به آن دسترسی دارند. انعطاف‌پذیر است ولی کندتر، چون هر دسترسی یک پیام است. برای ۸۰۰۰ افزایش از قفل استفاده کردم و جمع دقیق شد.
- {{< term "shared-memory" "SharedMemory" >}} یک بلوک خام حافظه است. فرزند با اسم به آن وصل شد و `hello` نوشت و والد آن را خواند. بعد `close()` و `unlink()` آزادش کردند و وصل شدن دوباره `FileNotFoundError` داد، که نشان می‌دهد چیزی نشت نکرد.

اگر ترجیح می‌دهید به‌جای اشتراک state پیام بفرستید، `mp.Queue` کار می‌کند: چهار فرزند هر کدام `(n, n*n)` داخلش گذاشتند و والد `[(0, 0), (1, 1), (2, 4), (3, 9)]` را گرفت.

## initializer و خطاها

pool می‌تواند یک تابع آماده‌سازی را یک بار در هر worker اجرا کند، که جای باز کردن اتصال یا بارگذاری یک مدل است. `Pool(2, initializer=init, initargs=('cfg',))` عبارت `init('cfg')` را در هر worker اجرا می‌کند و تابع کار `tagged` مقدار `['cfg:0', 'cfg:1', 'cfg:2']` را برگرداند، پس هر worker آماده‌سازی را دید.

وقتی worker یک exception پرتاب کند چه می‌شود؟ آن به والد فرستاده و دوباره پرتاب می‌شود، با traceback خود worker که به‌عنوان علتش ضمیمه است. این خروجی دمو است، با مسیرهای بلند کوتاه‌شده:

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

نیمه‌ی اول traceback از داخل worker است و خط واقعی خطا را نشان می‌دهد. نیمه‌ی دوم والد است که آن را در `pool.map` دوباره پرتاب می‌کند. دمو همچنین `caught: ValueError('bad input 2') | cause: RemoteTraceback` چاپ کرد و نسخه‌ی executor هم `bad input 2` را به همین شکل پرتاب کرد.

## thread، goroutine، worker_threads

threadها حافظه را مشترک دارند ولی یک GIL را، پس برای انتظار کمک می‌کنند و برای محاسبه نه. processها Python خالص را موازی اجرا می‌کنند، به بهای زمان راه‌اندازی و pickle. goroutine در Go ارزان است و حافظه را به اشتراک می‌گذارد ([goroutine و channel](/fa/posts/go-goroutines-channels/)). `worker_threads` در Node threadهای جدا با event loop خودشان هستند ([worker thread و cluster](/fa/posts/node-worker-threads-cluster/))؛ یک process در Python به یک مفسر کاملاً جدید نزدیک‌تر است.

## جاهایی که process گران می‌شود

- همیشه از محافظ `if __name__ == '__main__':` استفاده کنید. start method پیش‌فرض بین سیستم‌عامل‌ها فرق دارد، پس اسکریپتی که روی یکی کار می‌کند ممکن است روی دیگری خراب شود.
- تابع‌ها و آرگومان‌ها باید قابل pickle باشند. کارها را درشت نگه دارید تا کار هر وظیفه در مقایسه با داده‌ای که می‌فرستید بزرگ باشد.
- state قابل‌تغییر مشترک قفل می‌خواهد؛ معمولاً ساده‌تر است نتیجه‌ها را برگردانید و در والد ترکیب کنید.
- حافظه‌ی مشترک را آزاد کنید: `close()` را در هر process و `unlink()` را یک بار صدا بزنید.
- برای کار CPU از process استفاده کنید. برای انتظار، thread یا asyncio ارزان‌تر است.

## تمرین

یک شمارنده‌ی عدد اول بنویسید روی بازه‌ی ۰ تا ۲٬۰۰۰٬۰۰۰ که به ۸ تکه تقسیم شده باشد. اول با `Pool.map` و بعد با `ProcessPoolExecutor` اجرایش کنید. pid workerها را چاپ کنید تا ثابت شود بیش از یک process کار کرد، و فقط وقتی زمانش را بگیرید که `uptime` ماشین آرام را نشان بدهد.

## قدم بعدی

وقتی کار فقط انتظار است process سنگین است، پس پست بعد «asyncio در Python» است، راه تک‌threadی برای مدیریت هزاران کار منتظر.
