+++
date = '2027-05-04T10:00:00+03:30'
draft = false
title = 'timeout، retry و backoff با jitter'
description = 'timeout و retry درست در Go: کلاینت واقعی روی loopback، شبیه‌سازی retry storm با seed ثابت، retry budget، انتقال deadline و درخواست hedged.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "go", "retries", "backoff", "timeouts"]
cover = { image = "/images/covers/ds-timeouts-retries-backoff.fa.png", alt = "timeout، retry و backoff با jitter", hiddenInSingle = true }
+++

{{< term "deadline" "timeout" >}} فقط می‌گوید نمی‌دانید چه شد ([چرا سیستم توزیع‌شده سخت است](/fa/posts/ds-why-distributed-is-hard/))، و واکنش معمول retry است. در مقاله‌ی قبل، [ساعت منطقی](/fa/posts/ds-logical-clocks/)، رویدادها را بدون اعتماد به زمان مرتب کردیم؛ اینجا تصمیم می‌گیریم وقتی یک فراخوانی ساکت می‌شود چه کنیم. retry هم درمان است و هم از علت‌های کلاسیک قطعی. فقط برای عملیاتی که تکرارشان امن است معنا دارد ([idempotency در JetStream](/fa/posts/nats-jetstream-idempotency/)) و با [rate limiting](/fa/posts/go-rate-limiting-caching/) هم اثر متقابل دارد.

> صادقانه: بخش ۱ کلاینت و سرور HTTP واقعی روی loopback است (Go 1.26 و `httptest`) با شکست‌های seed‌دار. بخش‌های ۲ تا ۴ **شبیه‌سازی** هستند، با ساعت شبیه‌سازی‌شده و تصادف seed‌دار؛ شبکه‌ی شبیه‌سازی‌شده شبکه‌ی واقعی نیست. ماشین مشغول بود، پس فقط تعداد نشان می‌دهم، نه زمان. دمو یک مثال محلی است، نه repo.

## ۱. کلاینت واقعی در برابر سرور ناپایدار

سرور با قرعه‌ی seed‌دار خراب می‌شود: ۱۵٪ `503` با `Retry-After: 1`، ۱۵٪ آن‌قدر کند که از timeout ۱۰۰ms هر تلاش بگذرد، ۱۰٪ reset اتصال، بقیه `200`. کلاینت هر تلاش را با `context.WithTimeout` می‌پیچد، زیر یک deadline کلی است، حداکثر ۵ بار تلاش می‌کند و با backoff همراه jitter صبر می‌کند. `403` هرگز retry نمی‌شود.

```
logical requests: 31, attempts: 52, succeeded: 30, failed: 0
  HTTP 403 (not retried)       1
  HTTP 503                     8
  context deadline exceeded    6
  transport error              7
sample: Get "http://127.0.0.1:PORT/item/1": context deadline exceeded
sample: Get "http://127.0.0.1:PORT/item/3": read tcp 127.0.0.1:PORT->127.0.0.1:PORT: read: connection reset by peer
```

دو پیام خطا یک چیز نیستند: deadline یعنی کلاینت دست کشید (شاید سرور هنوز کار می‌کند)، reset یعنی اتصال قطع شد. قاعده‌هایی که رعایت می‌کنم:

- فقط عملیات idempotent یا دارای idempotency key را retry کن.
- فقط خطاهایی را که ممکن است برطرف شوند: timeout، خطای اتصال، `5xx`. هرگز `4xx`.
- اگر `Retry-After` از تأخیر خودت بیشتر بود، رعایتش کن.
- همه‌چیز محدود باشد: تعداد تلاش هر فراخوانی و یک deadline کلی.

## ۲. طوفان retry (شبیه‌سازی)

{{< term "retry-storm" "retry storm" >}}: ۱۰۰۰ کلاینت، سروری که در هر tick ۳۰۰ درخواست را جواب می‌دهد، قطعی در tickهای ۱ تا ۳ که هر درخواست شکست می‌خورد، و رد شدن هر چه بالاتر از ظرفیت است. هر کلاینت بعد از ۱۲ تلاش تسلیم می‌شود. فرمول‌ها را از مقاله‌ی «Exponential Backoff And Jitter» در AWS Architecture Blog به یاد دارم (جزئیات محتاطانه؛ پیاده‌سازی از خودم): base برابر ۲ و cap برابر ۳۲؛ {{< term "exponential-backoff" "نمایی" >}} `min(cap, base*2^n)`؛ full {{< term "jitter" "jitter" >}} عددی تصادفی در `[0, آن]`؛ equal jitter نصف به‌علاوه‌ی نصفِ تصادفی؛ decorrelated برابر `min(cap, random(base, prev*3))`.

```
strategy           requests   served  gaveUp  lastTk  peak
immediate              3800     1000       0       6   700
fixed 4                1900     1000       0       9   500
exp, no jitter         1900     1000       0      13   500
exp, full jitter       2254     1000       0      27   586
exp, equal jitter      1979     1000       0      11   500
decorrelated           1881     1000       0      12   500

exp, no jitter:   500 500 0 0 200 500 0 0 0 0 0 0 0 200
exp, full jitter: 500 586 247 221 191 158 65 57 58 64 55 22 1 6 5 2 4 ...
```

retry فوری تقریباً چهار درخواست به‌ازای هر کلاینت می‌فرستد. بدون jitter کلاینت‌ها هم‌زمان می‌مانند: موج‌های ۵۰۰ و ۲۰۰ و ۵۰۰ و ۲۰۰ با tickهای خالی میان آن‌ها. full jitter موج‌ها را به یک شیب تبدیل می‌کند، به قیمت دُم بلندتر (tick ۲۷) و درخواست کل بیشتر در این شبیه‌سازی. پس jitter یعنی «بار هموارتر»، نه «درخواست کمتر». طبق تجربه‌ی من همین همواری است که اجازه می‌دهد سرور در حال بهبود واقعاً بهبود پیدا کند. عددها به پارامترهای من بستگی دارند؛ نرخ عمومی نیستند.

## ۳. تقویت و retry budget (شبیه‌سازی)

سه لایه که هرکدام ۳ تلاش می‌کنند و سرویس انتهایی که از کار افتاده. هر لایه ضرب می‌کند: ۳ × ۳ × ۳ = ۲۷ درخواست به‌ازای هر فراخوانی کاربر به انتها می‌رسد. {{< term "retry-budget" "retry budget" >}} به هر لایه یک token bucket می‌دهد که به‌ازای هر درخواست ۰٫۱ توکن می‌گیرد و برای هر retry یکی خرج می‌کند (سقف ۱۰).

```
bottom fails 100%, budget=false: top calls 1000, ok 0, requests per layer [3000 9000 27000], last layer 27.00x
bottom fails 100%, budget=true : top calls 1000, ok 0, requests per layer [1222 1493 1824], last layer 1.82x
bottom fails  50%, budget=false: top calls 1000, ok 1000, requests per layer [1003 1145 1995], last layer 2.00x
bottom fails  50%, budget=true : top calls 1000, ok 760, requests per layer [1137 1305 1510], last layer 1.51x
```

budget در قطعی کامل خسارت را محدود می‌کند (۲۷ برابر به ۱٫۸۲)، ولی در خرابی جزئی موفقیت‌ها را کم می‌کند (اینجا ۷۶۰ از ۱۰۰۰). مبادله همین است: کمتر retry کن تا وابستگی محافظت شود. توصیه‌ی رایج این است که retry فقط در یک لایه باشد.

## ۴. بودجه‌ی deadline و hedging

برای کل درخواست یک deadline بگذارید و **زمان باقی‌مانده** را پایین بدهید. در یک زنجیره‌ی شبیه‌سازی‌شده که هر hop از بودجه‌ی ۳۰۰ms مقدار ۵۰ms خرج می‌کند:

```
gateway  sees remaining deadline 300 ms
orders   sees remaining deadline 250 ms
stock    sees remaining deadline 200 ms
db       sees remaining deadline 150 ms
```

با timeout ثابت ۳۰۰ms برای هر hop، دیتابیس می‌تواند مدت‌ها بعد از رفتن فراخواننده کار کند. gRPC این را با هدر `grpc-timeout` حمل می‌کند ([gRPC روی HTTP/2](/fa/posts/net-grpc-over-http2/)). timeout بیش از حد بلند منابع کمیاب مثل اتصال‌ها را هم نگه می‌دارد ([connection pooling](/fa/posts/db-connection-pooling/)).

{{< term "hedged-request" "درخواست hedged" >}} بعد از ۲۰ms نسخه‌ی دوم را می‌فرستد و اولین پاسخ را برمی‌دارد. تأخیرهای شبیه‌سازی‌شده، ۹۵٪ حدود ۱۰ms و ۵٪ بین ۲۰۰ تا ۳۰۰ms، با ۱۰۰۰۰ درخواست:

```
hedging: 10000 requests, >100 ms: 502 without hedge, 25 with hedge; extra requests sent: 502 (5.0%)
```

موارد کند از ۵۰۲ به ۲۵ رسید، با ۵٪ بار اضافه. شبیه‌سازی فرض می‌کند تأخیرها مستقل‌اند؛ در واقعیت کندی اغلب همبسته است.

## چند نکته‌ی مهم

- هر حلقه‌ی retry سقف تعداد تلاش و deadline کلی لازم دارد.
- به هر backoff جیتر بدهید؛ فایده‌ی production آن را اینجا اندازه نگرفتم.
- retry در چند لایه ضرب می‌شود؛ budget بگذارید یا متمرکزش کنید.
- timeout یعنی «نامعلوم»: اول عملیات را idempotent کنید.
- hedging به فراخوانی امن و تکرارپذیر و ظرفیت اضافه نیاز دارد.

## تمرین

در `sim.go` مقدار `capacity` را ۱۵۰ و `outageTo` را ۵ کنید. کدام استراتژی زودتر کلاینت‌ها را از دست می‌دهد؟ بعد یک قاعده‌ی `Retry-After` به سرور شبیه‌سازی‌شده اضافه کنید.

## قدم بعدی

مقاله‌ی بعدی «circuit breaker و bulkhead» است.
