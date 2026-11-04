+++
date = '2027-06-11T10:00:00+03:30'
draft = false
title = 'case study: rate limiter و سامانه‌ی اعلان'
description = "case study طراحی rate limiter و سامانه‌ی اعلان: نیازمندی، برآورد و شکست‌ها، با نسخه‌ی کوچک Go برای هر کدام که با بار seed دار اجرا شد."
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "system-design", "rate-limiting"]
cover = { image = "/images/covers/ds-case-studies.fa.png", alt = "case study: rate limiter و سامانه‌ی اعلان", hiddenInSingle = true }
+++

«یک rate limiter طراحی کن.» «یک سامانه‌ی اعلان طراحی کن.» این دو سؤال بارها پرسیده می‌شوند، هم در مصاحبه و هم در کار واقعی. جواب‌ها روی تخته همیشه قانع‌کننده به نظر می‌رسند. مشکل این است که کسی آن‌ها را نمی‌سنجد: state چند بایت جا می‌گیرد، وقتی یک node می‌رود دقیقاً چه می‌شود، و crash با پیامی که همین الان ارسال شده چه می‌کند؟

برای همین نسخه‌ی کوچکی از هر دو را در Go ساختم و روی بارهای seed‌دار اجرا کردم، تا ادعاها را بسنجم و فقط تکرارشان نکنم. نتیجه‌ای که اول بار مرا غافلگیر کرد این بود: در سامانه‌ی اعلان، یک پنجره‌ی crash باعث شد ۴ اعلان از ۱۰۰ تا دو بار ارسال شود و فقط idempotency key خودِ provider آن را بست. بقیه‌ی این مقاله راهی است که به چنین نتیجه‌ای می‌رسد.

هر case همین پنج گام را دارد: نیازمندی، عددهای تقریبی (حساب‌وکتابش از [مقاله‌ی قبل](/fa/posts/ds-capacity-estimation/) است)، بخش‌ها و انتخاب برای هرکدام، یک ساخت کوچک، و بعد حالت‌های خرابی. اگر فقط درس‌ها را می‌خواهید، آخر مقاله‌اند.

> دموها تا چه حد صادقانه‌اند: همه‌چیز روی یک ماشین است. «nodeها» shardهای درون‌process هستند، شبکه loopback است، senderها ساختگی‌اند، store در حافظه است (یک mutex نقش transaction را بازی می‌کند) و NATS توکار است. عددهای ترافیک فرضی‌اند، بارها seed‌دار، و شمارش چاپ می‌کنم، نه زمان‌سنجی. همه‌چیز را با Go 1.27 دوباره اجرا کردم و خروجی‌های زیر همان چیزی است که چاپ شد؛ اجرای دوم دموی اعلان هم دقیقاً همان را می‌دهد.

## case ۱: rate limiter به عنوان سرویس

وضعیت: یک API می‌خواهد تعداد درخواست‌های هر key (یک کاربر، یک token) را محدود کند. به‌جای اینکه هر سرور خودش بشمارد، یک سرویس limiter به سؤال «این درخواست مجاز است؟» جواب می‌دهد. نیازمندی‌هایی که فرض کردم: ۵ میلیون کاربر روزانه، هر کدام ۳۰ check در روز، اوج ۵ برابر میانگین، و از کار افتادن limiter نباید API را از کار بیندازد.

اول حساب. ۵٬۰۰۰٬۰۰۰ کاربر × ۳۰ check ÷ ۸۶٬۴۰۰ ثانیه ≈ ۱٬۷۳۶ check/s به‌طور میانگین، و با ضرب در ۵ حدود ۸٬۶۸۱ check/s در اوج. برای state، هر key یک شمارنده لازم دارد. هزینه‌ی ۱ میلیون key را در Go اندازه گرفتم (یک map، یک key ۱۶ بایتی و یک bucket) و ۱۳۶ بایت برای هر key شد؛ پس ۵ میلیون key فعال به ۵٬۰۰۰٬۰۰۰ × ۱۳۶ بایت ≈ ۰٫۶۸ گیگابایت نیاز دارد. همه در حافظه جا می‌شود.

```
avg checks/s        1736
peak checks/s (x5)  8681
measured bytes/key  136 (map + 16-byte key + bucket, 1M keys)
5M active keys      0.68 GB of state
```

حالا بخش‌ها و انتخاب من برای هرکدام:

| بخش | انتخاب |
|---|---|
| API | `POST /check {key, cost}` جواب `{allowed, remaining, retry_after_ms}` می‌دهد؛ API آن را به `X-RateLimit-Remaining` و `429` و `Retry-After` تبدیل می‌کند |
| الگوریتم‌ها | {{< term "token-bucket" "token bucket" >}} و {{< term "sliding-window" "sliding window counter" >}} پشت یک interface |
| state | به‌ازای هر key، در حافظه، shard شده روی nodeها با {{< term "consistent-hashing" "consistent hashing" >}} |
| کلاینت | {{< term "deadline" "deadline" >}} برای هر درخواست، بعد {{< term "fail-open" "fail open" >}} به یک bucket محلی |

چند مورد یک جمله توضیح لازم دارند. token bucket سطلی است که تا N توکن نگه می‌دارد و با نرخ ثابتی پر می‌شود؛ هر درخواست یک توکن برمی‌دارد و وقتی سطل خالی است درخواست رد می‌شود. sliding window counter به‌جای آن، درخواست‌های آخرین بازه‌ی زمانی را می‌شمارد. consistent hashing روشی برای سپردن keyها به nodeهاست که وقتی یک node می‌رود فقط keyهای همان به nodeهای دیگر منتقل شوند (پایین‌تر می‌شماریمشان). fail open یعنی وقتی خود limiter در دسترس نیست، کلاینت درخواست‌ها را عبور می‌دهد، به‌جای اینکه همه‌چیز را ببندد.

### دو الگوریتم

اجرای اول ۳۰۰ درخواست در ثانیه را به مدت ۱۰ ثانیه برای یک key می‌فرستد، با سقف ۱۰۰ در ثانیه:

```
token bucket 100/s burst 100   offered 3018 allowed 1099 max in any 1s window 199
sliding window 100 per 1s      offered 3018 allowed 991 max in any 1s window 102
token bucket ideal: burst 100 + 100/s*10s = 1100; sliding window ideal: 100 x 10 windows = 1000
```

هر خط نشان می‌دهد چند درخواست آمد، چندتا مجاز شد و بیشترین تعداد مجاز در یک بازه‌ی یک‌ثانیه‌ای چند بود. token bucket روی نرخ ثابت یک burst هم اجازه می‌دهد: با ۱۰۰ توکن پر شروع می‌کند، پس در ۱۰ ثانیه می‌تواند حدود ۱۰۰ + ۱۰۰ × ۱۰ = ۱۱۰۰ درخواست رد کند (۱۰۹۹ تا مجاز شد) و در یک ثانیه ۱۹۹ تا را رد کرد. window counter هموارتر است (حداکثر ۱۰۲ در هر ثانیه) ولی تقریبی: ۹۹۱ مجاز کرد، در حالی که حالت ایده‌آل ۱۰۰۰ است. اینکه کدام درست است به این بستگی دارد که burst برای شما ویژگی است یا مشکل. [محدودسازی توزیع‌شده](/fa/posts/ds-distributed-rate-limiting/) و [rate limiting در Go](/fa/posts/go-rate-limiting-caching/) را ببینید.

### از دست دادن یک node

وقتی state روی nodeها پخش است، رفتن یک node چه می‌کند؟ اجرا ۱۰۰۰ key دارد که هرکدام ۲۰ درخواست در ثانیه می‌فرستند در برابر سقف ۱۰ در ثانیه، ۴ node، و node به نام `n4` در t = ۵ ثانیه حذف می‌شود:

```
offered 200676 (1000 keys x 20/s x 10 s), limit 10/s burst 10 per key
keys that changed owner when n4 left: ring 288, hash mod N 731 (of 1000)
allowed, no failure 108202 | n4 removed at t=5s 110566 | extra 2364 (8.2 per moved key)
```

روی حلقه (ring) (ببینید [sharding](/fa/posts/ds-sharding-consistent-hashing/)) ۲۸۸ key صاحب‌شان عوض شد. با روش ساده‌ی «hash mod N» ۷۳۱ از ۱۰۰۰ key جابه‌جا می‌شد. keyای که جابه‌جا شود روی node تازه‌اش دوباره با یک bucket پر شروع می‌کند، پس limiter برای مدت کوتاهی بیش از حد عبور می‌دهد: ۲٬۳۶۴ درخواست اضافه از ۲۰۰٬۶۷۶، یعنی ۸٫۲ به‌ازای هر key جابه‌جاشده. این عبور اضافه به تعداد keyهای جابه‌جاشده ضرب در اندازه‌ی burst محدود است (اینجا ۲۸۸ × ۱۰ = ۲٬۸۸۰)، پس کوچک است و بی‌حد رشد نمی‌کند.

### یک hot key

sharding بر اساس key فرض می‌کند keyها تقریباً به یک اندازه شلوغ‌اند. اگر یک key ۶۰٪ ترافیک را بگیرد چه؟ اجرا ۲۰٬۰۰۰ check می‌فرستد و می‌شمارد روی هر node چندتا نشست؛ یک بار با hot key روی یک node و یک بار با شکستن آن به چهار sub-key که هرکدام یک‌چهارم سقف را دارند:

```
split=false checks per node n1..n4: 1930 1863 13878 2329 | hot key allowed 109
split=true  checks per node n1..n4: 4971 4863 4832 5334 | hot key allowed 108
```

بدون شکستن، یک node از ۲۰٬۰۰۰ check تعداد ۱۳٬۸۷۸ را گرفت و بقیه حدود ۲۰۰۰. با چهار sub-key بار تقریباً یکنواخت است و hot key هنوز تقریباً به همان تعداد درخواست محدود می‌شود (۱۰۹ در برابر ۱۰۸). این یک راه‌حل {{< term "hot-key" "hot key" >}} در یک خط است.

### کلاینت و headerها

در آخر سمت کلاینت روی HTTP loopback، با bucketای که هر ساعت یک توکن پر می‌شود تا پرشدن در طول اجرا اثری نداشته باشد. اول limiter با سقف ۵ بالاست، بعد متوقف می‌شود، بعد کند می‌شود (۳۰۰ms) در حالی که کلاینت deadline برابر ۵۰ms دارد:

```
-- limiter up (limit 5)
request 1: 200  X-RateLimit-Remaining=4 Retry-After=""
request 2: 200  X-RateLimit-Remaining=3 Retry-After=""
request 3: 200  X-RateLimit-Remaining=2 Retry-After=""
request 4: 200  X-RateLimit-Remaining=1 Retry-After=""
request 5: 200  X-RateLimit-Remaining=0 Retry-After=""
request 6: 429  X-RateLimit-Remaining=0 Retry-After="3600"
request 7: 429  X-RateLimit-Remaining=0 Retry-After="3600"
-- limiter stopped: client fails open to a local bucket (burst 2)
request 1: 200  X-RateLimit-Remaining=1 Retry-After=""
request 2: 200  X-RateLimit-Remaining=0 Retry-After=""
request 3: 429  X-RateLimit-Remaining=0 Retry-After="3600"
request 4: 429  X-RateLimit-Remaining=0 Retry-After="3600"
-- slow limiter (300 ms) with a 50 ms deadline: decision came from "local", fallbacks=1
```

تا وقتی limiter بالاست، تعداد باقی‌مانده ۴ و ۳ و ۲ و ۱ و ۰ می‌شود و درخواست ششم `429` می‌گیرد با `Retry-After` برابر ۳۶۰۰ ثانیه (زمان پر شدن یک توکن). وقتی limiter متوقف شود، کلاینت شکست نمی‌خورد: به یک bucket محلی کوچک با burst برابر ۲ برمی‌گردد، پس دو درخواست را مجاز می‌کند و بعد رد می‌کند. با limiter کند، deadline برابر ۵۰ms تمام می‌شود و تصمیم از bucket محلی می‌آید (`fallbacks=1`).

حالت‌های خرابی این طراحی: از دست رفتن node یعنی عبور اضافه‌ی کوتاه‌مدت (بالا اندازه گرفته شد)؛ limiter کند یا خاموش یعنی fail open که با bucket محلی محدود می‌شود. برای چیزی مثل login من fail closed را می‌گذارم، چون آنجا عبور دادن همه‌چیز جهت خطرناک است. hot key باید شکسته شود. چیزی که نساختم: gRPC و persistence.

## case ۲: سامانه‌ی اعلان

وضعیت: محصول شما باید ایمیل و SMS و push بفرستد. بعضی فوری‌اند (کد ورود)، بعضی نه (خبرنامه). provider (شرکتی که واقعاً ایمیل یا SMS را می‌رساند) کند است و گاهی خطا می‌دهد. نیازمندی‌هایی که فرض کردم: سه کانال، دو اولویت، ۳ میلیون اعلان در روز با اوج ۱۰ برابر نرخ میانگین، هر فراخوانی provider ۳۰۰ میلی‌ثانیه طول می‌کشد، ۹۹٪ پیام‌های اولویت بالا باید ظرف ۱۰ ثانیه ارسال شوند (این یک [SLO](/fa/posts/eng-sli-slo-error-budgets/) است)، و انصراف (opt-out) کاربر باید در لحظه‌ی ارسال رعایت شود.

| بخش | انتخاب |
|---|---|
| API | `POST /notify {user, template, channels, priority, idempotency_key}`؛ اعتبارسنجی، بعد یک transaction برای اعلان و ردیف‌های outbox |
| Relay | ردیف‌های outbox را با یک message id در {{< term "jetstream" "JetStream" >}} (جریان پایدار پیام در NATS) منتشر می‌کند ([outbox](/fa/posts/go-outbox-pattern-nats/)) |
| مسیرها | دو consumer به نام‌های `high` و `low`؛ اول `high` امتحان می‌شود ({{< term "priority-lane" "priority lane" >}}) |
| Worker | opt-out، ساعت سکوت، محدودیت برای هر کاربر (همان کد case ۱)، breaker، ارسال، و {{< term "dlq" "DLQ" >}} بعد از `MaxDeliver` تلاش |
| وضعیت | queued، sent، skipped، dead؛ «delivered» به webhook از provider نیاز دارد (نساخته‌ام) |

بخش «outbox» یک مشکل کلاسیک را حل می‌کند: چطور مطمئن شویم پیام دقیقاً وقتی منتشر می‌شود که تغییر دیتابیس commit شده باشد. API اعلان و ردیف‌های قابل‌انتشار را در یک transaction می‌نویسد و یک relay بعداً آن‌ها را منتشر می‌کند.

### چه چیزی اجرا شد

دمو هشت آزمایش را اجرا می‌کند. این خروجی کامل آن است (اجرای اول و دوم یکسان‌اند):

```
== E1 API idempotency and outbox
100 API calls, 40 distinct keys: notifications 40, deduped by key 60, rejected 0
validation: bad priority | bad channel fax
relay published 80 rows (2 channels each); crash-and-republish sent 80 more, JetStream duplicate acks 80, stream holds 80
== E2 priority lanes
queue depth before the worker runs: high 20, low 200
backlog: 200 low enqueued first, then 20 high; one worker
completions: 220, position of the last high-priority send: 20 (of 220)
== E3 retries and DLQ
200 emails, MaxDeliver 4, backoff 10/20/40 ms + jitter, provider: 30% 5xx, 10% timeout per attempt
sent on attempt 1/2/3/4: 131 / 45 / 15 / 5 | dead-lettered: 4 | provider calls: 302 (timeouts 25)
success rate 98.0% | retries scheduled 102
queue depth after: pending 0, ack-pending 0
== E4 crash windows
provider idempotency key=false crashes 13 | worker suppressed 9 redeliveries | provider accepted 104 sends for 100 notifications (4 notifications sent twice), provider deduped 0
provider idempotency key=true  crashes 13 | worker suppressed 9 redeliveries | provider accepted 100 sends for 100 notifications (0 notifications sent twice), provider deduped 4
== E5 preferences at send time
at 23:00 after alice opted out: statuses map[queued:1 sent:1 skipped:1], deferred (quiet hours, low priority) 1
at 08:00: statuses map[sent:2 skipped:1], opted-out skips 1
== E6 per-user rate limit
10 push notifications for one user, limit 20/s burst 3 (virtual clock): sent 10, limiter denials (nak + redelivery) 80, provider calls 12
== E7 fan-out
1 campaign -> 10000 recipients: 20 batches of 500, limiter waits 18, virtual time 1.8 s
published 10000, stream holds 10000 messages, 1780000 bytes (178 bytes per message)
-- capacity (invented traffic): 3M notifications/day, peak x10, provider latency 300 ms, 3-day retention
avg 35/s, peak 347/s, provider calls in flight at peak (Little) 104, stream 1.6 GB for 9M messages
== E8 circuit breaker
provider down, breaker=false: calls that reached the provider 240, rejected locally 0, dead-lettered 60
provider down, breaker=true : calls that reached the provider 28, rejected locally 212, dead-lettered 60
```

یکی‌یکی مرور می‌کنم.

**E1، API.** ۱۰۰ فراخوانی با فقط ۴۰ idempotency key متمایز، ۴۰ اعلان ساخت؛ ۶۰ تای دیگر به‌عنوان تکراری شناخته شدند. priority و channel نامعتبر رد می‌شود. relay ۸۰ ردیف منتشر کرد (۴۰ اعلان × ۲ کانال). بعد relayای را شبیه‌سازی کردم که بعد از انتشار و پیش از علامت‌زدن ردیف‌ها crash کرد: همان ۸۰ ردیف را دوباره منتشر کرد و JetStream با ۸۰ تأیید تکراری جواب داد، پس stream هنوز ۸۰ پیام دارد. message id باعث می‌شود انتشار دوباره بی‌ضرر باشد.

**E2، مسیرهای اولویت.** اول ۲۰۰ پیام اولویت پایین صف شد و بعد ۲۰ پیام اولویت بالا، با یک worker. چون worker همیشه اول `high` را امتحان می‌کند، آخرین پیام اولویت بالا در جایگاه ۲۰ از ۲۲۰ ارسال شد، نه ۲۲۰.

**E3، retry.** ۲۰۰ ایمیل در برابر providerای که در هر تلاش ۳۰٪ مواقع خطای 5xx می‌دهد و ۱۰٪ مواقع timeout می‌شود. هر پیام تا ۴ تلاش می‌گیرد و بین تلاش‌ها ۱۰ و ۲۰ و ۴۰ms به‌علاوه‌ی کمی jitter تصادفی صبر می‌کند (این {{< term "exponential-backoff" "exponential backoff" >}} است؛ [retry](/fa/posts/ds-timeouts-retries-backoff/) و [DLQ](/fa/posts/nats-jetstream-retry-dlq/) را ببینید). ۱۳۱ تا در تلاش اول ارسال شد، ۴۵ تا در دوم، ۱۵ تا در سوم و ۵ تا در چهارم. ۴ تا هیچ‌وقت موفق نشدند و به dead-letter queue رفتند، پس ۱۹۶ از ۲۰۰ (۹۸٫۰٪) ارسال شد، با ۳۰۲ فراخوانی provider در مجموع.

**E4، پنجره‌های crash.** آزمایشی که پشت ادعای ابتدای مقاله است. worker را در دو نقطه «crash» می‌دهم. اولی بعد از پذیرفتن پیام توسط provider و پیش از ثبت آن در worker است. دومی بعد از ثبت و پیش از تأیید (ack) به صف. در حالت دوم پیام دوباره تحویل داده می‌شود و worker از ثبت خودش می‌بیند که قبلاً ارسال شده، پس تکرار را حذف می‌کند: ۹ تحویل دوباره حذف شد. در حالت اول worker هیچ ثبتی ندارد، پس هنگام تحویل دوباره دوباره می‌فرستد: provider ۱۰۴ ارسال را برای ۱۰۰ اعلان پذیرفت و ۴ اعلان دوبار رفت. با idempotency keyای که provider رعایت می‌کند، خود provider ۴ تکرار را کنار گذاشت (`provider deduped 4`) و کسی اعلان تکراری نگرفت.

**E5، ترجیحات در لحظه‌ی ارسال.** سه پیام صف شد: یک promo با اولویت پایین برای alice، یک promo با اولویت پایین برای bob، و یک کد با اولویت بالا برای bob. bob از ۲۲ تا ۲۴ ساعت سکوت دارد. بعد از صف‌شدن پیام‌ها، alice ایمیل را opt-out کرد. در ساعت ۲۳:۰۰ worker پیام alice را به‌خاطر opt-out رد کرد، کد اولویت بالای bob را فرستاد و promo bob را به‌خاطر ساعت سکوت عقب انداخت (در وضعیت `queued` می‌ماند). در ساعت ۰۸:۰۰ promo عقب‌افتاده هم ارسال شد و پیام opt-out‌شده همچنان رد شد. نکته این است که opt-out در لحظه‌ی ارسال اعمال شد، با اینکه بعد از صف‌شدن پیام آمده بود.

**E6، محدودیت برای هر کاربر.** ۱۰ اعلان push برای یک کاربر، با سقف ۲۰ در ثانیه و burst برابر ۳، روی ساعت مجازی. هر ۱۰ تا در نهایت ارسال شد. limiter ۸۰ تلاش را رد کرد؛ هر رد باعث می‌شود پیام صبر کند و دوباره تحویل شود.

**E7، fan-out.** یک کمپین برای ۱۰٬۰۰۰ گیرنده یک فراخوانی API است که به ۲۰ دسته‌ی ۵۰۰تایی تبدیل می‌شود و نرخ آن محدود می‌شود (limiter ۱۸ بار publisher را منتظر گذاشت، یعنی ۱٫۸ ثانیه‌ی مجازی). stream ده‌هزار پیام در ۱٬۷۸۰٬۰۰۰ بایت دارد، یعنی ۱۷۸ بایت برای هر پیام. برای عددهای ظرفیت: ۳٬۰۰۰٬۰۰۰ ÷ ۸۶٬۴۰۰ ≈ ۳۵ اعلان/ثانیه به‌طور میانگین و ۳۴۷ در ثانیه در اوج؛ با {{< term "littles-law" "قانون Little" >}} ۳۴۷ × ۰٫۳ ثانیه ≈ ۱۰۴ فراخوانی provider در جریان؛ و با ۳ روز نگهداری، ۹ میلیون پیام × ۱۷۸ بایت ≈ ۱٫۶ گیگابایت.

**E8، breaker.** وقتی provider کاملاً خاموش است، سیستم بدون breaker ۲۴۰ فراخوانی به provider زد (۶۰ پیام × ۴ تلاش) و ۶۰ پیام را dead-letter کرد. با breaker شمارشی ساده (بعد از ۵ خطا باز می‌شود و هر دهمین فراخوانی را به‌عنوان probe رد می‌کند) فقط ۲۸ فراخوانی به provider رسید و ۲۱۲ تا محلی رد شد. هر دو همان ۶۰ پیام را dead-letter کردند. breaker از provider محافظت می‌کند و کار را کم می‌کند، ولی پیام‌ها را نجات نمی‌دهد ([breakerها](/fa/posts/ds-circuit-breaker-bulkhead/)).

### مرور خرابی‌ها

| خرابی | نتیجه در اجراهای من |
|---|---|
| provider خاموش، بدون breaker | ۲۴۰ فراخوانی، ۶۰ DLQ |
| provider خاموش، با breaker (بعد از ۵ خطا باز می‌شود، هر دهمین فراخوانی probe است) | ۲۸ فراخوانی، ۶۰ DLQ |
| crash بعد از پذیرفتن provider و پیش از ثبت | ۴ از ۱۰۰ دوبار ارسال شد؛ با idempotency key در provider، صفر |
| crash بعد از ثبت و پیش از ack | ۹ تحویل دوباره با جدول sent حذف شد |
| crash در relay بعد از انتشار | JetStream ردیف‌های دوباره‌منتشرشده را کنار می‌گذارد |
| NATS خاموش | این را اجرا نکردم؛ ردیف‌ها در outbox منتظر می‌مانند |

ردیف اول crash همان لبه‌ی اجتناب‌ناپذیر {{< term "at-least-once-delivery" "at-least-once" >}} است: اگر نتوانید بفهمید پیام ارسال شده یا نه، یا خطر ارسال دوباره را می‌پذیرید یا خطر ارسال‌نشدن را. تنها راه واقعی این است که فراخوانی provider هم idempotent باشد ([idempotency](/fa/posts/nats-jetstream-idempotency/)).

چند محدودیت صادقانه. اجرای breaker همه‌چیز را dead-letter می‌کند، چون provider شبیه‌سازی‌شده هرگز برنمی‌گردد؛ یک سیستم واقعی باید پیام‌ها را نگه دارد و بعداً دوباره تلاش کند. در E3، ۹۸٫۰٪ ایمیل‌ها ارسال شد، ولی باید با هدف ۹۹٪ محتاط باشم: آن SLO درباره‌ی سرعت ارسال پیام‌های اولویت بالاست و E3 نه زمان را اندازه می‌گیرد و نه اولویت را؛ فقط می‌توانم بگویم ۴ ایمیل از ۲۰۰ به dead-letter queue رفت. به تجربه‌ی من راه‌حل این مورد یک provider دوم است، نه retry بیشتر. در آخر، ترتیب مسیرها می‌تواند به هم بخورد: اگر یک پاسخ کند از `high` با یک مسیر خالی اشتباه گرفته شود، worker اول پیام `low` را برمی‌دارد. دمو به همین دلیل به مسیر `high` شلوغ انتظار طولانی‌تری می‌دهد.

## درس‌های مشترک هر دو طراحی

- **هر عددی اینجا شبیه‌سازی‌شده یا فرضی است.** آن‌ها را شکل بخوانید و سیستم خودتان را اندازه بگیرید.
- **fail open یا fail closed را پیش از حادثه انتخاب کنید**، نه وسط آن.
- **ترجیحات را در لحظه‌ی ارسال بررسی کنید**، نه وقتی پیام صف می‌شود، چون در این فاصله می‌توانند عوض شوند.
- **تکراری‌ها را در provider هم بشمارید.** ثبت‌های خودتان ارسالی را که مطمئن نیستید اتفاق افتاده نمی‌بینند.
- **به سنِ قدیمی‌ترین پیام نگاه کنید**، نه فقط طول صف ([observability](/fa/posts/nats-jetstream-observability/)).

## قدم بعدی

مقاله‌ی بعدی «پروژه‌ی پایانی توزیع‌شده» است، آخرین مقاله‌ی این سری. قطعه‌های همه‌ی مقاله‌ها را در یک پروژه کنار هم می‌گذارد.
