+++
date = '2027-06-03T10:00:00+03:30'
draft = false
title = 'rate limit توزیع‌شده'
description = 'rate limit توزیع‌شده با Go: چرا N limiter محلی بیش از حد می‌پذیرند، مقایسه‌ی الگوریتم‌های پنجره‌ای، limiter دقیق با CAS روی NATS KV و حالت‌های خرابی.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "rate-limiting", "nats", "kv", "go"]
cover = { image = "/images/covers/ds-distributed-rate-limiting.fa.png", alt = "rate limit توزیع‌شده", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-service-discovery-load-balancing/) درخواست‌ها را بین چند replica پخش کرد. این کار limitی را که روی یک ماشین درست کار می‌کرد خراب می‌کند: token bucket تک‌پردازه‌ی [rate limit و cache در Go](/fa/posts/go-rate-limiting-caching/) حالا N بار وجود دارد. اینجا «۱۰۰ در ثانیه» باید در کل ناوگان ۱۰۰ باشد.

> صادقانه: جز بخش NATS همه‌چیز **شبیه‌سازی** Go 1.26 با seed ثابت روی یک ماشین است و شمارش نشان می‌دهم، نه زمان. بخش NATS واقعی است: nats-server توکار روی loopback. Redis را اجرا نکردم.

## N limiter محلی

چهار کلاینت هرکدام حدود ۵۰۰ req/s به‌مدت ۱۰ ثانیه می‌فرستند. هر replica برای هر کلاینت {{< term "token-bucket" "token bucket" >}} خودش را دارد: ۱۰۰ req/s و burst برابر ۱۰. مجموع ایده‌آل حدود ۴۰۴۰ است.

```
N=1  sticky=true  offered=19875 allowed=4036
N=3  sticky=true  offered=19875 allowed=4036
N=3  sticky=false offered=19922 allowed=12097
N=10 sticky=false offered=19922 allowed=19922
```

با مسیریابی تصادفی limit عملاً N برابر می‌شود و در N=10 هیچ چیز محدود نمی‌شود. مسیریابی sticky با کلید کلاینت (ببینید [consistent hashing](/fa/posts/algo-bloom-filter-consistent-hashing/)) شمارنده را روی یک replica نگه می‌دارد، به قیمت {{< term "hot-key" "hot key" >}}ها.

## الگوریتم‌ها روی ترافیک یکسان

همان ۴۹۵ درخواست، limit برابر ۱۰۰ در ۱۰۰۰ms: نویز، یک burst با ۱۰۰ درخواست درست قبل از مرز ۱۰۰۰ms، یکی درست بعد از آن و یکی میانه‌ی پنجره.

```
algorithm                 allowed   max/1000ms in[950,1050) diff-exact
fixed window                  436          199          180        135
sliding log (exact)           351          100           81          0
sliding counter               355          104           84         10
token bucket (cap 20)         247           49           29        124
leaky meter (cap 20)          247           49           29        124
```

fixed window در ۱۰۰ms تعداد ۱۸۰ درخواست و در یک ثانیه ۱۹۹ درخواست را رد کرد، تقریباً دو برابر limit، چون شمارنده در مرز صفر می‌شود. sliding log دقیق است ولی تا ۱۰۰ timestamp برای هر کلید نگه می‌دارد. {{< term "sliding-window" "sliding window counter" >}} دو عدد نگه می‌دارد و از ۴۹۵ تصمیم ۱۰ تصمیم متفاوت گرفت، با حداکثر ۱۰۴ در یک ثانیه. token bucket و leaky meter دقیقاً یکسان تصمیم گرفتند (با تست). هر دو burst را می‌پذیرند.

| | حافظه برای هر کلید | دقت | رفتار burst |
|---|---|---|---|
| fixed window | ۲ عدد | تا ۲ برابر در مرز | burst دوبل |
| sliding log | O(limit) | دقیق | ندارد |
| sliding counter | ۳ عدد | تقریبی | خطای کوچک |
| token / leaky | ۲ عدد | دقیق در مدل خودش | به اندازه‌ی ظرفیت |

## store مشترک با compare-and-set

حالا اجرای واقعی. یک bucket از JetStream KV (ببینید [KV و Object Store در NATS](/fa/posts/nats-kv-object-store/)) یک شمارنده نگه می‌دارد. سه goroutine، هرکدام با اتصال جدا، ۶۰۰ تلاش در برابر limit برابر ۱۰۰۰ انجام می‌دهند. نسخه‌ی ساده می‌خواند و می‌نویسد. نسخه‌ی CAS از `Update` با revisionی که خوانده استفاده می‌کند و در شکست دوباره تلاش می‌کند؛ همان ایده‌ی {{< term "optimistic-concurrency" "optimistic concurrency" >}}.

```
naive  limit=1000 attempts=1800 granted=[600 600 600] total=1800 final-counter=729 cas-conflicts=0
cas    limit=1000 attempts=1800 granted=[323 351 326] total=1000 final-counter=1000 cas-conflicts=1518
```

نسخه‌ی ساده هر ۱۸۰۰ درخواست را پذیرفت و به‌روزرسانی‌ها را گم کرد: شمارنده هرگز به limit نرسید. نسخه‌ی CAS دقیقاً ۱۰۰۰ مجوز داد و ۱۵۱۸ تعارض هزینه داد. تعارض‌ها در هر اجرا فرق می‌کنند، limit نه. در production اغلب Redis با `INCR`، `EXPIRE`، اسکریپت Lua یا GCRA به کار می‌رود؛ اجرایشان نکردم.

## تماس کمتر با store: توکن‌های اجاره‌ای

تماس با store برای هر درخواست تأخیر اضافه می‌کند. به‌جایش هر replica تعداد B توکن می‌گیرد و محلی خرج می‌کند. شبیه‌سازی: ۳ replica، limit برابر ۱۰۰۰ در هر پنجره، ثانیه‌های زوج کم‌ترافیک و فرد پرترافیک، توکن‌های خرج‌نشده نگه داشته می‌شوند.

```
B=1   store-calls=16485 busiest-window=1000
B=10  store-calls=  669 busiest-window=1017
B=50  store-calls=  150 busiest-window=1097
B=100 store-calls=   85 busiest-window=1197
```

تماس با store تا ۱۹۰ برابر کم می‌شود، به قیمت پذیرش بیش از حد: توکن‌های یک پنجره‌ی کم‌ترافیک در پنجره‌ی بعد خرج می‌شوند. کران من limit + N·B است چون هر replica حداکثر B توکن نگه می‌دارد؛ تست بررسی‌اش می‌کند ولی اثبات نیست.

## حالت‌های خرابی

**خاموشی store.** ثانیه‌های ۴ و ۵ بدون store، حدود ۱۵۰ req/s ورودی، limit برابر ۱۰۰:

```
fail open              served-in-outage= 307 rejected-in-outage=   0
fail closed            served-in-outage=   0 rejected-in-outage= 307
local fallback (L/3)   served-in-outage= 198 rejected-in-outage= 109
```

طبق تجربه‌ی من: برای login و endpointهای گران fail closed، برای خواندن‌های ارزان fail open، و در میان local fallback.

**clock skew.** replicaهایی که شناسه‌ی پنجره را از ساعت خودشان می‌سازند، با skew برابر ۰ و ۲+ و ۲- ثانیه، روی شناسه‌ی ۲۰۰۸۷ درخواست اختلاف داشتند و در دو ثانیه‌ی اول ۳۰۰ و ۲۰۰ درخواست پذیرفتند؛ در کل ۱۳۰۰ به‌جای ۱۰۰۰. با ساعت store هر ثانیه ۱۰۰ بود.

**retry storm.** ۵۰۰ کلاینت، limit برابر ۱۰۰ در ثانیه، retry بعد از ۴۲۹:

```
retry every 50 ms                      attempts= 20254 peak-retries-per-100ms=800
Retry-After (next window)              attempts=  1500 peak-retries-per-100ms=400
Retry-After + jitter 0-1 s             attempts=  1500 peak-retries-per-100ms= 50
full-jitter backoff (100 ms, cap 8 s)  attempts=  2358 peak-retries-per-100ms=274
```

`Retry-After` تعداد تلاش‌ها را ۱۳ برابر کم کرد و jitter قله را صاف کرد؛ ببینید [timeout، retry و backoff](/fa/posts/ds-timeouts-retries-backoff/).

**عدالت و هزینه.** با limit سراسری ۱۰۰۰، tenantی که ۵۰۰۰ درخواست فرستاد ۸۹۸ گرفت و سه tenant با ۲۰۰ درخواست فقط ۳۳ تا ۳۶. سقف ۳۰۰ برای هر tenant نتیجه را ۳۰۰ و ۲۰۰ و ۲۰۰ و ۲۰۰ کرد؛ پس limit سلسله‌مراتبی. برای ۳۰۰ درخواست read (هزینه ۱) و write (هزینه ۵)، limit تعدادی ۱۰۰ هزینه‌ی ۲۰۸ را پذیرفت و بودجه‌ی ۱۰۰ فقط ۴۴ درخواست.

## چند نکته‌ی مهم

- limit را در یک نقطه بررسی کنید، وگرنه N برابر می‌شود.
- پیش از خاموشی fail open یا closed را برای هر endpoint تعیین کنید.
- `Retry-After` بفرستید.

## تمرین

در آزمایش عدالت، برای هر tenant یک سطح کاربر اضافه کنید و بررسی کنید هیچ سقفی رد نمی‌شود.

## قدم بعدی

مقاله‌ی بعد: «تست خرابی با تزریق خطا».
