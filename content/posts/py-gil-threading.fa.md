+++
date = '2027-03-31T10:00:00+03:30'
draft = false
title = 'GIL و threading'
description = 'GIL و threading در Python: قفل چه می‌کند، thread کجا کمک می‌کند، race با lost update در build آزاد از GIL و Lock، Queue و thread pool.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "gil", "threading", "concurrency", "free-threading"]
cover = { image = "/images/covers/py-gil-threading.fa.png", alt = "GIL و threading", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-testing-pytest/) کدمان را تست کردیم؛ حالا هم‌زمانش می‌کنیم. اگر از Go ([goroutine و channel](/fa/posts/go-goroutines-channels/)) یا Node.js ([event loop](/fa/posts/node-event-loop/)) آمده باشید، اولین شگفتی Python همان {{< term "gil" "GIL" >}} است: در CPython استاندارد در هر لحظه فقط یک {{< term "thread" "thread" >}} بایت‌کد Python را اجرا می‌کند. این مقاله با اجراهای واقعی نشان می‌دهد این یعنی چه.

> بیشتر دموها با Python 3.14.0 (`python3 --version`) و با GIL اجرا شد، و برای یک مقایسه Python 3.14.3 آزاد از GIL (`python3.14t`، نصب با `uv python install 3.14t` و بعداً پاک‌شده). `sys._is_gil_enabled()` به ترتیب `True` و `False` چاپ کرد. ماشین زیر بار سنگین بود، پس **هیچ زمانی برای کار CPU** منتشر نمی‌کنم؛ تنها زمانِ این مقاله مربوط به `sleep` است.

## thread وقتی انتظار دارد کمک می‌کند

وقتی thread روی I/O یا `sleep` بلاک می‌شود، GIL آزاد می‌شود و بقیه اجرا می‌شوند. ده کار از نوع `time.sleep(0.2)`:

```text
sequential, 10 x 0.2s: ~2.0s
10 threads:           ~0.2s [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

زمان گردشده ده برابر کم شد، چون sleep انتظار است نه محاسبه. کد از `ThreadPoolExecutor(max_workers=10)` و `ex.map(fetch, range(10))` استفاده کرد؛ ساده‌ترین API: یک {{< term "thread-pool" "thread pool" >}} که نتیجه‌ها را به ترتیب ورودی برمی‌گرداند.

برای کار CPU-bound با Python خالص، GIL یعنی thread‌ها نوبتی کار می‌کنند و چهار thread چهار برابر سرعت نمی‌دهد. این را **اندازه نگرفتم**، چون بار ماشین هر عددی را بی‌معنا می‌کرد. طبق مستندات برای کار CPU از process استفاده کنید؛ موضوع مقاله‌ی بعد.

## raceی که GIL جلویش را نمی‌گیرد

{{< term "race-condition" "race condition" >}} به موازی‌بودن نیاز ندارد، فقط یک جابه‌جایی thread بین دو قدم کافی است. ۸ thread گرفتم که هرکدام ۲۰۰٬۰۰۰ بار `counter += 1` می‌زنند، سه بار اجرا:

```text
no lock   run 1: 1600000 expected 1600000
no lock   run 2: 1600000 expected 1600000
no lock   run 3: 1600000 expected 1600000
```

روی 3.14.0 هیچ update از دست نرفت، و وقتی دستور را به `tmp = counter; counter = tmp + 1` شکستم هم چیزی از دست نرفت. نتیجه نگیرید که امن است: `+=` چند بایت‌کد است و interpreter می‌تواند بینشان thread را عوض کند (فاصله‌ی پیش‌فرض `sys.getswitchinterval()` اینجا ۰٫۰۰۵ ثانیه بود). فقط در اجراهای من اتفاق نیفتاد. همین فایل روی 3.14.3 آزاد از GIL:

```text
no lock   run 1: 215326 expected 1600000
no lock   run 2: 209878 expected 1600000
no lock   run 3: 252377 expected 1600000
with lock run 1: 1600000 expected 1600000
```

حالا حدود ۸۵٪ افزایش‌ها گم شد، چون thread‌ها واقعاً موازی اجرا می‌شوند (ببینید {{< term "free-threading" "Python آزاد از GIL" >}}). راه‌حل روی هر دو build یکی است، یک {{< term "mutex" "lock" >}}:

```python
lock = threading.Lock()
for _ in range(N):
    with lock:
        counter += 1
```

هر سه اجرای «with lock» روی هر دو build دقیقاً ۱٬۶۰۰٬۰۰۰ شد. درس: GIL از interpreter محافظت می‌کند، نه از داده‌ی شما.

## worker pool با queue.Queue

{{< term "queue" "queue.Queue" >}} از قبل thread-safe است و تمیزترین راه تحویل کار بین thread‌هاست. سه worker، ده کار، و برای هر worker یک sentinel به شکل `None` که یعنی «بایست»:

```python
def worker():
    while True:
        item = q.get()
        if item is None:
            q.task_done(); break
        out.put(item * item); q.task_done()
```

`q.join()` صبر می‌کند تا همه‌ی آیتم‌ها done شوند؛ خروجی مرتب‌شده `[0, 1, 4, 9, ..., 81]` بود. این همان الگوی {{< term "worker-pool" "worker pool" >}} در [الگوهای concurrency در Go](/fa/posts/go-concurrency-patterns/) است.

## متوقف‌کردن thread و تله‌ی daemon

راهی برای کشتن thread از بیرون نیست. از `threading.Event` استفاده کنید: worker روی `while not stop.wait(0.05)` می‌چرخد (خوابی که با set‌شدن event فوراً بیدار می‌شود) و main اول `stop.set()` و بعد `join()` می‌زند. worker دموی من بعد از چند tick چاپ کرد که stop را دید.

{{< term "daemon-thread" "daemon thread" >}} (با `daemon=True`) فرق دارد: وقتی thread اصلی تمام شود process خارج می‌شود و daemon رها می‌شود، بدون اجرای cleanup. daemon من در `sleep(60)` بود و کل اسکریپت در ۰٫۳ ثانیه تمام شد.

## کوتاه: asyncio، Go و Node

`asyncio` گزینه‌ی سوم است: یک thread، یک {{< term "event-loop" "event loop" >}} و `await`؛ برای تعداد زیاد socket عالی است، مثل Node. goroutine در Go را runtime خودِ Go روی چند thread سیستم‌عامل زمان‌بندی می‌کند، پس کار CPU در goroutine‌ها موازی اجرا می‌شود. `worker_threads` در Node جاوااسکریپت را در thread‌های جدا با event loop مخصوص خودشان اجرا می‌کند؛ [Worker threads و cluster در Node.js](/fa/posts/node-worker-threads-cluster/) را ببینید.

## چند نکته‌ی مهم

- thread برای انتظار (شبکه، دیسک، `sleep`)، process برای محاسبه.
- یک اجرای سالم چیزی درباره‌ی race ثابت نمی‌کند. داده‌ی mutable مشترک را قفل کنید یا با `Queue` ردش کنید.
- همیشه `join()` بزنید یا از `with ThreadPoolExecutor(...)` استفاده کنید تا exceptionهای worker گم نشوند.
- cleanup مهم را در daemon thread نگذارید.
- build آزاد از GIL گزینه است نه پیش‌فرض؛ من فقط روی همین مثال کوچک امتحانش کردم و ممکن است کتابخانه‌ها هنوز پشتیبانی نکنند.

## تمرین

اسکریپتی بنویسید که با thread pool پنج‌تایی ۲۰ صفحه از یک `http.server` محلی بگیرد و بشمارد چند تا قبل از تمام‌شدن اولی شروع شدند. بعد شمارنده را مشترک کنید و روی build آزاد از GIL قفل را بردارید تا افت را ببینید.

## قدم بعدی

مقاله‌ی بعد «multiprocessing در Python» است، جایی که کار CPU-bound بالاخره از همه‌ی هسته‌ها استفاده می‌کند.
