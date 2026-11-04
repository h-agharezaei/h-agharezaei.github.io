+++
date = '2027-03-31T10:00:00+03:30'
draft = false
title = 'GIL و threading'
description = 'GIL و threading در Python: قفل چه می‌کند، thread کجا کمک می‌کند، race با lost update در build آزاد از GIL و Lock، Queue و thread pool.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "gil", "threading", "concurrency", "free-threading"]
cover = { image = "/images/covers/py-gil-threading.fa.png", alt = "GIL و threading", hiddenInSingle = true }
+++

فرض کنید تابعی دارید که ده ثانیه عدد پردازش می‌کند. کار را بین چهار {{< term "thread" "thread" >}} تقسیم می‌کنید، روی لپ‌تاپ چهار هسته‌ای اجرا می‌کنید و انتظار دارید حدود سه ثانیه طول بکشد. در Python استاندارد این‌طور نمی‌شود، چون threadها به‌جای اینکه با هم اجرا شوند نوبتی کار می‌کنند. دلیلش اسم دارد، {{< term "gil" "GIL" >}}، و اولین چیزی است که کسانی را که از Go ([goroutine و channel](/fa/posts/go-goroutines-channels/)) یا Node.js ([event loop](/fa/posts/node-event-loop/)) می‌آیند غافلگیر می‌کند.

GIL یک قفل واحد در مفسر استاندارد Python (به نام CPython) است. thread برای اجرای کد Python باید آن را در دست داشته باشد و فقط یکی از آن وجود دارد. پس حتی با چهار thread روی چهار هسته، در هر لحظه فقط یکی از آن‌ها bytecode پایتون اجرا می‌کند. مثل جلسه‌ای با یک میکروفون: همه می‌توانند در اتاق باشند، ولی فقط کسی که میکروفون دستش است حرف می‌زند.

این به فاجعه شبیه است، پس بهتر است دقیق ببینیم چه چیزی را مسدود می‌کند و چه چیزی را نه. بعد از [تست کردن کد](/fa/posts/py-testing-pytest/)، این پست آن را هم‌زمان می‌کند و به سه سؤال جواب می‌دهد: threadها کِی کمک می‌کنند، با آن‌ها چه چیزی هنوز می‌تواند خراب شود، و وقتی کمک نمی‌کنند چه باید کرد.

> دموها را با Python 3.14.0 اجرا کردم (`python3 --version`)، نسخه‌ی استاندارد با GIL: `sys._is_gil_enabled()` مقدار `True` چاپ کرد. مقایسه با نسخه‌ای بدون GIL، در بخش race، از اجرای اصلی همین پست روی Python 3.14.3 free-threaded است (`python3.14t`، نصب‌شده با `uv python install 3.14t` و بعدش پاک‌شده) که `sys._is_gil_enabled()` در آن `False` چاپ کرد؛ آن نسخه را دوباره نصب نکردم، پس دوباره اجرایش نکرده‌ام. ماشین شلوغ بود (میانگین بار یک‌دقیقه‌ای هنگام اجرای دوباره‌ی دموها بالای ۱۰)، برای همین برای کار CPU **هیچ زمانی منتشر نمی‌کنم**. تنها زمان نمایش‌داده‌شده یک sleep است که به بار ماشین وابسته نیست. دموها اسکریپت‌های محلی هستند.

## تصویر: یک میکروفون

این یک طرح‌واره از دو thread است که هر دو محاسبه می‌کنند، زیر GIL (نقشه‌ی ایده است، نه اندازه‌گیری). `A` و `B` threadها هستند و نقطه یعنی «در آن لحظه کد Python اجرا نمی‌کند»:

```text
CPU-bound, 2 threads, with the GIL:
  thread A:  AAAA....AAAA....AAAA
  thread B:  ....BBBB....BBBB....
  (one thread at a time; the interpreter hands the GIL over every so often)

I/O-bound, 2 threads, with the GIL:
  thread A:  A~~~~~~~~~~~~~~~~~~A     ~ = waiting (sleep, socket), GIL released
  thread B:  .B~~~~~~~~~~~~~~~~~B
  (both wait at the same time; each holds the GIL only for its short bursts of Python code)
```

دو نکته در این تصویر مهم است. وقتی دو thread محاسبه می‌کنند نوبتی کار می‌کنند، پس کل کار در ثانیه با یک thread برابر است. وقتی یک thread منتظر است GIL را می‌دهد، پس بقیه اجرا می‌شوند و انتظارها روی هم می‌افتند. همین یک تفاوت تعیین می‌کند threadها کِی ارزش دارند.

## threadها وقتی منتظرند کمک می‌کنند

وقتی thread روی I/O (تماس شبکه، خواندن فایل) یا `sleep` بلاک می‌شود، GIL آزاد می‌شود و threadهای دیگر اجرا می‌شوند. برای دیدنش بدون شبکه، دموی `io.py` از `time.sleep(0.2)` به‌جای انتظار شبکه استفاده می‌کند. ده کار، اول پشت سر هم و بعد در ده thread:

```text
sequential, 10 x 0.2s: ~2.0s
10 threads:           ~0.2s [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

پشت سر هم، ده انتظار روی هم حدود ۲ ثانیه می‌شود. با ده thread، هر ده با هم منتظر می‌مانند و کل زمان تقریباً یک انتظار است، ۰٫۲ ثانیه. زمان سپری‌شده ده برابر کم شد، چون sleep یعنی انتظار نه محاسبه. (این دو عدد تا یک رقم اعشار گرد شده‌اند و sleepها بر آن‌ها غالب‌اند، پس بار ماشین عوضشان نمی‌کند.) کد از `ThreadPoolExecutor(max_workers=10)` و `ex.map(fetch, range(10))` استفاده کرد. این ساده‌ترین API برای threadها است: یک {{< term "thread-pool" "thread pool" >}} که تابع را در threadهایش اجرا می‌کند و نتیجه‌ها را به ترتیب ورودی برمی‌گرداند.

برای کد Python خالصِ CPU-bound تصویر همان اولی است: threadها نوبتی کار می‌کنند، پس چهار thread چهار برابر سرعت نمی‌دهند. من این را **اندازه نگرفتم**، چون بار ماشین هر عددی را بی‌معنی می‌کرد. طبق مستندات Python، برای کار CPU از processها استفاده کنید؛ پست بعد همین است.

## race که GIL جلویش را نمی‌گیرد

یک نتیجه‌گیری غلط رایج این است: «فقط یک thread در هر لحظه اجرا می‌شود، پس داده‌ی مشترک من امن است.» نیست. {{< term "race-condition" "race condition" >}} به موازی بودن نیاز ندارد؛ فقط به یک جابه‌جایی thread بین دو قدم از یک عملیات نیاز دارد. ببینید Python چطور `counter += 1` را اجرا می‌کند. این bytecode تابعی است که این کار را روی یک متغیر سراسری می‌کند (در یک اسکریپت scratch با ماژول `dis` چاپ شد):

```text
LOAD_GLOBAL              0 (counter)
LOAD_SMALL_INT           1
BINARY_OP               13 (+=)
STORE_GLOBAL             0 (counter)
```

یک خط Python چهار قدم است: خواندن مقدار، بار کردن ۱، جمع، ذخیره. اگر thread A مقدار `5` را بخواند، بعد مفسر به thread B بپرد که او هم `5` را می‌خواند، یکی اضافه می‌کند و `6` ذخیره می‌کند، و بعد A به `5` قدیمی‌اش یکی اضافه کند و او هم `6` ذخیره کند، یک افزایش گم شده است. مفسر می‌تواند بین bytecodeها thread را عوض کند؛ فاصله‌ی پیش‌فرض جابه‌جایی با `sys.getswitchinterval()` خوانده می‌شود که اینجا `0.005` ثانیه چاپ کرد.

دموی `race.py` هشت thread اجرا می‌کند که هر کدام ۲۰۰٬۰۰۰ بار `counter += 1` می‌زنند، سه بار بدون قفل. جمع مورد انتظار ۱٬۶۰۰٬۰۰۰ است. روی 3.14.0 با GIL:

```text
no lock   run 1: 1600000 expected 1600000
no lock   run 2: 1600000 expected 1600000
no lock   run 3: 1600000 expected 1600000
```

هیچ افزایشی گم نشد، حتی در `race2.py` که جمله را دستی به `tmp = counter` و `counter = tmp + 1` شکستم (آن هم `1600000` چاپ کرد). لطفاً این را «امن است» نخوانید. فقط یعنی در این اجراها جابه‌جایی در لحظه‌ی بد اتفاق نیفتاد. کد هنوز غلط است و نسخه‌ی free-threaded آن را نشان می‌دهد. این همان فایل است روی Python 3.14.3 بدون GIL، از اجرای اصلی (به {{< term "free-threading" "Python بدون GIL" >}} نگاه کنید):

```text
no lock   run 1: 215326 expected 1600000
no lock   run 2: 209878 expected 1600000
no lock   run 3: 252377 expected 1600000
with lock run 1: 1600000 expected 1600000
```

این‌جا حدود ۸۵٪ افزایش‌ها از بین رفتند، چون threadها واقعاً هم‌زمان اجرا می‌شوند و مدام نتیجه‌ی همدیگر را رونویسی می‌کنند. راه‌حل روی هر دو نسخه یکی است، یک {{< term "mutex" "قفل" >}}:

```python
lock = threading.Lock()
for _ in range(N):
    with lock:
        counter += 1
```

در هر لحظه فقط یک thread می‌تواند داخل `with lock:` باشد، پس خواندن، جمع و ذخیره‌ی یک thread تمام می‌شود پیش از اینکه thread دیگری شروع کند. هر سه اجرای «with lock» دقیقاً ۱٬۶۰۰٬۰۰۰ دادند روی 3.14.0 (و روی نسخه‌ی free-threaded در اجرای اصلی). درس: GIL از داده‌های خود مفسر محافظت می‌کند، نه از داده‌ی شما.

## worker pool با queue.Queue

قفل را راحت می‌شود فراموش کرد. راه آرام‌تر برای تقسیم کار بین threadها این است که کار را از یک {{< term "queue" "queue.Queue" >}} عبور بدهید که خودش thread-safe است: یک thread چیزی داخلش می‌گذارد، thread دیگری برمی‌دارد و هیچ‌کس به یک متغیر دست نمی‌زند. دموی `pool.py` سه worker راه می‌اندازد، ده کار در صف می‌گذارد و بعد به ازای هر worker یک `None` می‌گذارد که نشانه‌ی «کار تمام شد، بایست» است (sentinel):

```python
def worker():
    while True:
        item = q.get()
        if item is None:
            q.task_done(); break
        out.put(item * item); q.task_done()
```

هر worker یک عنصر برمی‌دارد، مجذورش را حساب می‌کند و نتیجه را در صف دوم می‌گذارد. `task_done()` به صف می‌گوید یک عنصر پردازش شد و `q.join()` در thread اصلی صبر می‌کند تا همه‌ی عنصرها تمام‌شده علامت بخورند. خروجی مرتب‌شده این بود:

```text
[0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
```

(مرتبش می‌کنم چون workerها با ترتیب ثابتی تمام نمی‌کنند.) این همان الگوی {{< term "worker-pool" "worker pool" >}} در [الگوهای concurrency در Go](/fa/posts/go-concurrency-patterns/) است، این بار با thread و صف.

## متوقف کردن threadها و daemon thread

راهی برای کشتن thread از بیرون نیست. از آن می‌خواهید بایستد و او باید موافقت کند. ابزار معمول `threading.Event` است. در دموی `event.py` worker روی `while not stop.wait(0.05)` حلقه می‌زند، یعنی یک خواب ۵۰ میلی‌ثانیه‌ای که با set شدن event فوراً بیدار می‌شود. بعد از ۰٫۳ ثانیه thread اصلی `stop.set()` و بعد `join()` را صدا می‌زند. خروجی این بود:

```text
worker saw stop after some ticks
```

{{< term "daemon-thread" "daemon thread" >}} (`daemon=True`) فرق دارد. وقتی thread اصلی تمام می‌شود، فرایند خارج می‌شود و daemonها همان لحظه رها می‌شوند، بدون اینکه کد پاک‌سازی‌شان اجرا شود. در همین دمو یک daemon thread در `sleep(60)` نشسته بود و اسکریپت باز هم فوراً تمام شد و چاپ کرد:

```text
main exits; daemon thread is killed, its cleanup never runs
```

## asyncio، Go و Node در یک نگاه

`asyncio` گزینه‌ی سوم کنار thread و process است: یک thread، یک {{< term "event-loop" "event loop" >}} و `await`. برای تعداد زیادی socket که هم‌زمان منتظرند عالی است، با همان روحیه‌ی Node؛ دو پست بعد درباره‌اش است. goroutine در Go را runtime خود Go روی چند thread سیستم‌عامل زمان‌بندی می‌کند، پس کار CPU در goroutineها موازی اجرا می‌شود، دقیقاً همان کاری که threadهای Python نمی‌توانند. `worker_threads` در Node جاوااسکریپت را در threadهای جدا اجرا می‌کند و هر کدام event loop خودشان را دارند؛ [worker thread و cluster در Node.js](/fa/posts/node-worker-threads-cluster/) را ببینید.

## جاهایی که thread کم می‌آورد

- thread برای انتظار (شبکه، دیسک، `sleep`) و process برای محاسبه.
- یک اجرای موفق درباره‌ی race چیزی ثابت نمی‌کند، همان‌طور که سه اجرای تمیز بالا نشان داد. داده‌ی قابل‌تغییر مشترک را قفل کنید یا از `Queue` ردش کنید.
- همیشه threadها را `join()` کنید یا از `with ThreadPoolExecutor(...)` استفاده کنید تا exceptionهای داخل workerها گم نشوند.
- پاک‌سازی مهم را در daemon thread نگذارید: وقتی برنامه خارج می‌شود اجرا نمی‌شود.
- نسخه‌های free-threaded یک گزینه‌اند نه پیش‌فرض. من فقط روی همین مثال کوچک یکی را امتحان کردم و ممکن است کتابخانه‌ها هنوز پشتیبانی نکنند.

## تمرین

اسکریپتی بنویسید که ۲۰ صفحه را از یک `http.server` محلی با thread pool با اندازه‌ی ۵ بگیرد و بشمارد چند تا شروع شدند پیش از اینکه اولی تمام شود. بعد شمارنده را مشترک کنید و روی نسخه‌ی free-threaded قفل را بردارید تا از دست رفتن را ببینید.

## قدم بعدی

چون thread نمی‌تواند Python خالص را موازی محاسبه کند، پست بعد «multiprocessing در Python» است، جایی که کار CPU-bound بالاخره از همه‌ی هسته‌ها استفاده می‌کند.
