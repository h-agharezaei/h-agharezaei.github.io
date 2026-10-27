+++
date = '2027-04-14T10:00:00+03:30'
draft = false
title = 'asyncio در Python'
description = 'asyncio در Python: coroutine و task، TaskGroup، لغو و timeout، فریز شدن loop با کد بلاک‌کننده، Queue، Semaphore و یک echo server با TCP.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "asyncio", "concurrency", "async", "taskgroup"]
cover = { image = "/images/covers/py-asyncio.fa.png", alt = "asyncio در Python", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-multiprocessing/) برای کار CPU از process استفاده کردیم. برای انتظار روی socket، `asyncio` گزینه‌ی سوم کنار thread است (ببینید [GIL و threading](/fa/posts/py-gil-threading/)). اگر Node.js بلد باشید ([event loop](/fa/posts/node-event-loop/)، [Promise و async/await](/fa/posts/node-promises-async-await/)) بیشترش آشناست؛ جالب‌ترین بخش تفاوت‌هاست.

> Python 3.14.0 و فقط کتابخانه‌ی استاندارد. ماشین زیر بار سنگین بود، پس تعداد، ترتیب و boolean منتشر می‌کنم و **هیچ زمانی** نه. اسکریپت‌های دمو نمونه‌های محلی‌اند.

## coroutine و task

تابع `async def` با صدا زدن یک {{< term "coroutine" "coroutine" >}} برمی‌گرداند؛ فقط وقتی `await` شود یا روی {{< term "event-loop" "event loop" >}} زمان‌بندی شود اجرا می‌شود. هر کار start را لاگ می‌کند، ۰٫۱ ثانیه می‌خوابد و end را لاگ می‌کند. سه کار، یکی‌یکی با await و بعد با `asyncio.gather`:

```text
sequential: ['start 0', 'end 0', 'start 1', 'end 1', 'start 2', 'end 2']
gather    : ['start 0', 'start 1', 'start 2', 'end 0', 'end 1', 'end 2'] [0, 1, 2]
```

`await job()` کار را تا انتها اجرا می‌کند و بعد جلو می‌رود. `gather` هر coroutine را در یک task می‌پیچد، پس همه قبل از پایان اولی شروع می‌شوند. با ده task در `asyncio.TaskGroup`، ۱۰ رویداد قبل از اولین «end 0» لاگ شد و نتیجه‌ها به ترتیب ساخت `[0, ..., 9]` بود.

همه روی یک thread اجرا شدند: `threading.get_ident()` را از ده task جمع کردم و `len(ids) == 1` مقدار `True` داشت و برابر id ‌ی thread اصلی بود. task‌ها فقط در `await` عوض می‌شوند، پس برای state ساده‌ی درون حافظه بین دو await معمولاً lock لازم نیست.

## کد بلاک‌کننده، loop را فریز می‌کند

یک task شمارنده را هر ۱۰ میلی‌ثانیه زیاد می‌کند. وقتی یک coroutine `time.sleep(0.5)` صدا می‌زد، تغییر شمارنده این بود:

```text
ticks during blocking time.sleep(0.5): 0
ticks during to_thread(time.sleep, 0.5): True
```

صفر tick: هیچ‌کس دیگر اجرا نشد. با `await asyncio.to_thread(time.sleep, 0.5)` فراخوانی به یک thread می‌رود و ticker ادامه داد (فقط چاپ کردم که دست‌کم ۲۰ tick گرفت، نه عدد دقیق). `loop.run_in_executor` همین کار را با executor صریح می‌کند. درس همان کار طولانی همگام در Node است. در Go فرق دارد: goroutine‌ها را runtime روی چند thread سیستم‌عامل زمان‌بندی می‌کند و بلاک شدن یکی بقیه را متوقف نمی‌کند ([goroutine و channel](/fa/posts/go-goroutines-channels/)).

## فراموش کردن await

```python
async def forgot():
    asyncio.sleep(0.1)   # no await
asyncio.run(forgot())
```

```text
<string>:4: RuntimeWarning: coroutine 'sleep' was never awaited
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
```

coroutine ساخته و دور ریخته شد. برخلاف Promise در JavaScript، اصلاً شروع نمی‌شود. با `python3 -X dev` traceback بلندتری از محل ساخت می‌گیرید.

## لغو و timeout

`task.cancel()` در `await` فعلیِ task یک `CancelledError` پرتاب می‌کند. خروجی:

```text
slow: cleanup, got CancelledError
cancelled: True
timeout() -> TimeoutError
wait_for -> TimeoutError
```

task بلوک `except` را اجرا کرد، دوباره پرتاب کرد و `t.cancelled()` برابر `True` شد. بعد از cleanup همیشه `CancelledError` را دوباره پرتاب کنید. `async with asyncio.timeout(0.1)` و `await asyncio.wait_for(coro, 0.1)` هر دو خواب ۵ ثانیه‌ای را به `TimeoutError` تبدیل کردند (از 3.11 builtin است).

## TaskGroup: structured concurrency

`TaskGroup` یک {{< term "structured-concurrency" "structured concurrency" >}} است: هیچ taskی از بلوک `async with` بیرون نمی‌ماند و وقتی یکی شکست بخورد بقیه لغو می‌شوند. یک خوابِ طولانی و دو task را راه انداختم که در ۱۰ و ۲۰ میلی‌ثانیه `ValueError` و `KeyError` پرتاب می‌کنند:

```text
sibling cancelled by TaskGroup
ValueError group: ['bad value']
```

خطاها در یک {{< term "exception-group" "ExceptionGroup" >}} می‌رسند و با `except*` مدیریت می‌شوند (ببینید [خطاها و context manager](/fa/posts/py-errors-context-managers/)). شاخه‌ی `KeyError` چیزی چاپ نکرد: گروه آن task را قبل از پرتاب لغو کرد. پس همیشه همه‌ی خطاها را نمی‌بینید، فقط آن‌هایی را که پیش از لغو رخ دادند.

## Queue و Semaphore

یک `asyncio.Queue(maxsize=2)` بین یک تولیدکننده و یک مصرف‌کننده {{< term "backpressure" "backpressure" >}} می‌دهد: وقتی صف پر است `put` منتظر می‌ماند. مصرف‌کننده شش عدد را به توان دو رساند: `[0, 1, 4, 9, 16, 25]`.

برای سقف گذاشتن روی هم‌زمانی از {{< term "semaphore" "semaphore" >}} استفاده کنید. بیست task، `asyncio.Semaphore(3)` و شمارنده‌ی taskهای داخل بلوک:

```text
semaphore limit 3, peak concurrent: 3
```

اوج دقیقاً برابر سقف بود، پس این یک بررسی قطعی است.

## echo server با TCP

```python
async def handle(r, w):
    while data := await r.readline():
        w.write(data.upper()); await w.drain()
    w.close(); await w.wait_closed()

srv = await asyncio.start_server(handle, "127.0.0.1", 0)
```

port صفر یعنی سیستم‌عامل یک port آزاد انتخاب کند. پنج client هم‌زمان با `gather` وصل شدند و هرکدام خطش را با حروف بزرگ گرفت:

```text
['HELLO 0', 'HELLO 1', 'HELLO 2', 'HELLO 3', 'HELLO 4']
```

یک thread هر پنج اتصال را سرویس داد. با [سرور TCP از صفر](/fa/posts/net-sockets-tcp-from-scratch/) مقایسه کنید.

## چند نکته‌ی مهم

- در coroutine هرگز کد بلاک‌کننده (`time.sleep`، `requests`، CPU سنگین) صدا نزنید؛ از `to_thread` یا process pool استفاده کنید.
- coroutine‌ها را همیشه `await` کنید و به هشدار `never awaited` توجه کنید.
- `TaskGroup` را به `create_task` خالی ترجیح دهید و به taskهایی که می‌سازید reference نگه دارید.
- `CancelledError` را دوباره پرتاب کنید، قورتش ندهید.
- روی هر فراخوانی شبکه timeout بگذارید.

## تمرین

اسکریپتی بنویسید که ۳۰ URL را از یک `http.server` محلی با `open_connection` و semaphore پنج‌تایی بگیرد و اوج هم‌زمانی را چاپ کند. بعد `asyncio.timeout(0.5)` اضافه کنید و یکی از URLها را کند کنید.

## قدم بعدی

مقاله‌ی بعد «ساخت API با FastAPI و Pydantic» است، جایی که handler‌های `async def` روی همین event loop اجرا می‌شوند.
