+++
date = '2027-04-14T10:00:00+03:30'
draft = false
title = 'asyncio در Python'
description = 'asyncio در Python: coroutine و task، TaskGroup، لغو و timeout، فریز شدن loop با کد بلاک‌کننده، Queue، Semaphore و یک echo server با TCP.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "asyncio", "concurrency", "async", "taskgroup"]
cover = { image = "/images/covers/py-asyncio.fa.png", alt = "asyncio در Python", hiddenInSingle = true }
+++

یک معما. قرار است یک کار کوچک هر ۱۰ میلی‌ثانیه یک بار تیک بزند. کار دیگری در کنارش `time.sleep(0.5)` را صدا می‌زند. کار اول در آن نیم‌ثانیه چند تیک می‌زند؟ پنجاه تا؟ نه، صفر. یک فراخوانی بلاک‌کننده همه‌چیز را متوقف کرد، و فهمیدن دلیلش کلید فهمیدن `asyncio` است.

فرض کنید هزار تماس شبکه دارید و هر کدام تقریباً تمام وقتش را منتظر جواب می‌ماند. می‌توانید هزار thread راه بیندازید، ولی سنگین است. `asyncio` راه دیگری می‌رود: **یک thread، و کارهایی که هر وقت باید منتظر بمانند مؤدبانه کنار می‌روند**. وقتی یک کار منتظر جوابش است، thread سراغ کار دیگری می‌رود. همه‌چیز روی یک thread است و فقط در کلمه‌ی `await` جابه‌جا می‌شود.

این گزینه‌ی سوم هم‌زمانی در Python است، کنار thread (به [GIL و threading](/fa/posts/py-gil-threading/) نگاه کنید) و processهایی که برای کار CPU در [پست قبلی](/fa/posts/py-multiprocessing/) به کار بردیم. برای منتظر ماندن روی socketها ساخته شده، نه برای محاسبه. اگر Node.js را می‌شناسید ([event loop](/fa/posts/node-event-loop/)، [Promise و async/await](/fa/posts/node-promises-async-await/)) بیشترش آشنا به نظر می‌رسد. تفاوت‌ها جاهایی هستند که جالب می‌شود.

> همه‌ی دموها را دوباره با Python 3.14.0 اجرا کردم، فقط با کتابخانه‌ی استاندارد. ماشین شدیداً شلوغ بود (میانگین بار یک‌دقیقه‌ای بین ۱۱ و ۱۴)، برای همین شمارش‌ها، ترتیب‌ها و مقدارهای بولی را منتشر می‌کنم، **بدون هیچ زمانی**. اسکریپت‌های دمو مثال‌های محلی هستند.

## ایده در یک تصویر

تابع `async def` تابعی است که می‌تواند مکث کند. در `await` مکث می‌کند و فقط همان‌جا. برنامه‌ای که تصمیم می‌گیرد بعد کدام کار اجرا شود {{< term "event-loop" "event loop" >}} است. این ردی از دو کار است که هر کدام کمی کار می‌کنند، منتظر می‌مانند و تمام می‌شوند:

```text
time ->
task A:  [run A] await sleep ........................ [run A: finish]
task B:           [run B] await sleep ............................ [run B: finish]
loop:    A runs until its await, then B runs until its await,
         then the loop has nothing to do and waits for a timer to fire.
```

دقت کنید که هیچ‌کس کاری را وسط راه قطع نمی‌کند. هر کار تا رسیدن به `await` اجرا می‌شود و فقط بعد از آن loop می‌رود سراغ بعدی. به این می‌گویند چندوظیفگی همکارانه. ساده و قابل‌پیش‌بینی است، و معمای بالا را هم توضیح می‌دهد: کاری که هرگز به `await` نمی‌رسد هرگز به کسی اجازه‌ی اجرا نمی‌دهد.

## coroutine و task

وقتی یک تابع `async def` را صدا می‌زنید، بدنه‌اش اجرا نمی‌شود. یک {{< term "coroutine" "coroutine" >}} پس می‌گیرید، شیئی که یعنی «این فراخوانی، هنوز شروع‌نشده». فقط وقتی اجرا می‌شود که `await`ش کنید یا برای زمان‌بندی به event loop بدهیدش. coroutineای که loop خودش اجرایش می‌کند *task* نام دارد.

در دموی `d1.py` هر job عبارت `start` را لاگ می‌کند، ۰٫۱ ثانیه می‌خوابد، `end` را لاگ می‌کند و شماره‌اش را برمی‌گرداند. اول سه job که یکی‌یکی await شدند، بعد همان سه job با `asyncio.gather`:

```text
sequential: ['start 0', 'end 0', 'start 1', 'end 1', 'start 2', 'end 2']
gather    : ['start 0', 'start 1', 'start 2', 'end 0', 'end 1', 'end 2'] [0, 1, 2]
```

`await job()` job را تا آخر اجرا می‌کند و بعد به خط بعدی می‌رود، پس لاگ دقیقاً start، end، start، end است. `gather` هر coroutine را در یک task می‌پیچد، پس هر سه پیش از اینکه یکی تمام شود شروع می‌شوند: لاگ سه start را نشان می‌دهد و بعد سه end. فهرست آخر نتیجه‌ها را به ترتیب دارد. بعد دمو ده task را در یک `asyncio.TaskGroup` به کار برد (پایین‌تر بیشتر درباره‌اش):

```text
taskgroup: started before first end: 10 results: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

عدد، جای `end 0` در لاگ است، پس هر ۱۰ رویداد `start` اول آمدند و نتیجه‌ها به ترتیب ساخته‌شدن برگشتند.

همه‌ی این‌ها روی یک thread اجرا شد. دمو `threading.get_ident()` را از ده task جمع کرد و در یک set گذاشت:

```text
one thread for all tasks: True same as main: True
```

set یک عضو داشت، برابر شناسه‌ی thread اصلی. چون taskها فقط در `await` جابه‌جا می‌شوند، برای داده‌ی ساده‌ی درون حافظه بین دو await معمولاً به قفل نیاز ندارید: کسی نمی‌تواند وسط بپرد.

## فراخوانی بلاک‌کننده loop را منجمد می‌کند

حالا معما. دموی `d2.py` یک task ticker راه می‌اندازد که هر ۱۰ میلی‌ثانیه به یک شمارنده یکی اضافه می‌کند (بین افزایش‌ها `await asyncio.sleep(0.01)`). بعد اندازه می‌گیرد شمارنده در حالی که یک coroutine دیگر نیم‌ثانیه بلاک می‌شود چقدر رشد کرد، به دو روش:

```text
ticks during blocking time.sleep(0.5): 0
ticks during to_thread(time.sleep, 0.5): True
```

با `time.sleep(0.5)` ساده جواب ۰ است: sleep هرگز کنترل را پس نمی‌دهد، پس ticker حتی یک بار هم اجرا نشد. با `await asyncio.to_thread(time.sleep, 0.5)` فراخوانی بلاک‌کننده در یک thread جدا اجرا می‌شود و event loop آزاد می‌ماند، پس ticker به کارش ادامه داد. برای حالت دوم فقط چاپ می‌کنم که شمارنده دست‌کم ۲۰ تا رشد کرد یا نه، نه عدد دقیق، چون عدد دقیق به ماشین بستگی دارد. `loop.run_in_executor` همین کار را با executorی که خودتان انتخاب می‌کنید می‌کند.

درس همان درس یک کار synchronous طولانی در Node است: **هیچ‌وقت کد بلاک‌کننده را مستقیم در coroutine اجرا نکنید**. Go اینجا فرق دارد: goroutineها را runtime روی چند thread سیستم‌عامل زمان‌بندی می‌کند، پس فراخوانی بلاک‌کننده‌ی یک goroutine بقیه را متوقف نمی‌کند ([goroutine و channel](/fa/posts/go-goroutines-channels/)).

## فراموش کردن await

رایج‌ترین اشتباه مبتدی صدا زدن تابع coroutine بدون `await` است:

```python
async def forgot():
    asyncio.sleep(0.1)   # no await
asyncio.run(forgot())
```

```text
<demo>/d1.py:36: RuntimeWarning: coroutine 'sleep' was never awaited
  asyncio.sleep(0.1)   # no await
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
```

فراخوانی یک شیء coroutine ساخت و دورش انداخت، پس sleep هرگز اتفاق نیفتاد. برخلاف promise در JavaScript، coroutine تا await نشود حتی شروع نمی‌شود. Python وقتی شیء پاک می‌شود هشدار می‌دهد. اگر با `python3 -X dev` اجرا کنید، هشدار محل ساخته‌شدن coroutine را هم چاپ می‌کند.

## لغو و timeout

برای همیشه منتظر ماندن باگ است، پس taskها باید قابل لغو باشند. `task.cancel()` یک `CancelledError` را داخل task پرتاب می‌کند، در همان `await`ای که الان مکث کرده. در `d3.py` یک task ده ثانیه می‌خوابد، خطا را برای پاک‌سازی می‌گیرد و دوباره پرتابش می‌کند. بعد دو راه برای گذاشتن محدودیت زمانی روی یک sleep پنج‌ثانیه‌ای:

```text
slow: cleanup, got CancelledError
cancelled: True
timeout() -> TimeoutError
wait_for -> TimeoutError
```

خط اول بلوک `except` خود task است که اجرا شد. بعدش `t.cancelled()` مقدار `True` بود. همیشه بعد از پاک‌سازی `CancelledError` را دوباره پرتاب کنید، چون لغو باید کامل شود. هم `async with asyncio.timeout(0.1)` و هم `await asyncio.wait_for(coro, 0.1)` خواب طولانی را به `TimeoutError` تبدیل کردند. این همان `TimeoutError` داخلی در Python 3.11 و بعد از آن است.

## TaskGroup: structured concurrency

`TaskGroup` راهی است برای راه انداختن چند task با اطمینان از اینکه هیچ‌کدام فراموش نمی‌شود. {{< term "structured-concurrency" "structured concurrency" >}} است: هیچ taskی از بلوک `async with` فرار نمی‌کند، بلوک منتظر همه‌شان می‌ماند و وقتی یکی شکست بخورد بقیه لغو می‌شوند. در دمو یک خوابیده‌ی طولانی راه انداختم و دو task که در ۱۰ میلی‌ثانیه `ValueError` و در ۲۰ میلی‌ثانیه `KeyError` پرتاب می‌کنند:

```text
sibling cancelled by TaskGroup
ValueError group: ['bad value']
```

`ValueError` اول آمد، پس گروه خوابیده را لغو کرد و او پیامش را چاپ کرد. شکست‌ها با هم به شکل یک {{< term "exception-group" "ExceptionGroup" >}} می‌رسند و `except*` آن‌ها را بر اساس نوع مدیریت می‌کند (به [خطا و context manager](/fa/posts/py-errors-context-managers/) نگاه کنید). ببینید چه چیزی نیست: شاخه‌ی `KeyError` من هرگز چاپ نشد. آن task در ۱۰ میلی‌ثانیه لغو شد، پیش از اینکه انتظار ۲۰ میلی‌ثانیه‌ای‌اش تمام شود، پس هرگز پرتاب نکرد. گروه از خطاهایی خبر می‌دهد که پیش از لغو اتفاق افتادند، نه از هر خطایی که می‌توانست اتفاق بیفتد.

## Queue و Semaphore

دو ابزار وقتی کمک می‌کنند که taskها باید کار را بینشان تقسیم کنند. یک `asyncio.Queue(maxsize=2)` بین یک تولیدکننده و یک مصرف‌کننده {{< term "backpressure" "backpressure" >}} می‌دهد: وقتی صف دو عنصر دارد، `put` صبر می‌کند تا مصرف‌کننده یکی بردارد، پس تولیدکننده‌ی سریع نمی‌تواند مصرف‌کننده‌ی کند را سیل‌زده کند. مصرف‌کننده‌ی دمو شش عدد را به توان دو رساند و `[0, 1, 4, 9, 16, 25]` جمع شد.

برای محدود کردن تعداد taskهایی که هم‌زمان کاری می‌کنند از {{< term "semaphore" "semaphore" >}} استفاده کنید، شمارنده‌ای که فقط N task را داخل یک بلوک راه می‌دهد. دمو بیست task را با `asyncio.Semaphore(3)` راه می‌اندازد و می‌شمارد چند تا هم‌زمان داخل‌اند:

```text
semaphore limit 3, peak concurrent: 3
```

اوج دقیقاً برابر حد بود. به زمان‌بندی وابسته نیست، پس بررسی قابل‌اعتمادی است.

## یک سرور echo با TCP

بالاخره کاربردی که `asyncio` برایش ساخته شده: اتصال‌های زیاد روی یک thread. این سرور از هر کلاینت یک خط می‌خواند و با حروف بزرگ پسش می‌فرستد:

```python
async def handle(r, w):
    while data := await r.readline():
        w.write(data.upper()); await w.drain()
    w.close(); await w.wait_closed()

srv = await asyncio.start_server(handle, "127.0.0.1", 0)
```

پورت 0 می‌گذارد سیستم‌عامل یک پورت آزاد انتخاب کند. پنج کلاینت دمو هم‌زمان با `gather` وصل می‌شوند، هر کدام `hello <i>` می‌فرستد و یک خط پس می‌گیرد:

```text
['HELLO 0', 'HELLO 1', 'HELLO 2', 'HELLO 3', 'HELLO 4']
```

یک thread به هر پنج اتصال سرویس داد و در هر `await` جابه‌جا شد. اگر می‌خواهید همین را بدون `asyncio` ببینید، با [سرور TCP از صفر](/fa/posts/net-sockets-tcp-from-scratch/) مقایسه‌اش کنید.

## تله‌های asyncio

- هرگز کد بلاک‌کننده (`time.sleep`، `requests`، کار سنگین CPU) را داخل coroutine صدا نزنید. از `to_thread` یا یک process pool استفاده کنید.
- همیشه coroutineها را `await` کنید و وقتی هشدار `never awaited` را دیدید بخوانیدش.
- `TaskGroup` را به `create_task` خالی ترجیح بدهید و به هر taskای که می‌سازید ارجاعی نگه دارید تا گم نشود.
- `CancelledError` را دوباره پرتاب کنید؛ قورتش ندهید.
- روی هر تماس شبکه timeout بگذارید. بدون آن، یک طرف ساکت می‌تواند باعث شود یک task برای همیشه منتظر بماند.

## تمرین

اسکریپتی بنویسید که ۳۰ URL را از یک `http.server` محلی از طریق `open_connection` بگیرد، با semaphore به اندازه‌ی ۵، و اوج هم‌زمانی را چاپ کند. بعد `asyncio.timeout(0.5)` اضافه کنید و یکی از URLها را کند کنید.

## قدم بعدی

تابع `async def` فقط وقتی به کار می‌آید که چیزی اجرایش کند، پس پست بعد «ساخت API با FastAPI و Pydantic» است، جایی که handlerهای `async def` روی همین event loop اجرا می‌شوند.
