+++
date = '2027-06-11T10:00:00+03:30'
draft = false
title = 'case study: rate limiter و سامانه‌ی اعلان'
description = "case study طراحی rate limiter و سامانه‌ی اعلان: نیازمندی، برآورد و شکست‌ها، با نسخه‌ی کوچک Go برای هر کدام که با بار seed دار اجرا شد."
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "system-design", "rate-limiting"]
cover = { image = "/images/covers/ds-case-studies.fa.png", alt = "case study: rate limiter و سامانه‌ی اعلان", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-capacity-estimation/) حساب‌وکتاب را داد. این مقاله سری را روی دو سؤال کلاسیک مصاحبه می‌برد و از هر کدام نسخه‌ای کوچک می‌سازد تا ادعاها بررسی شده باشند.

> برچسب صادقانه: یک ماشین. «نودها» shardهای درون‌پروسه‌اند، شبکه loopback است، senderها ساختگی‌اند، store در حافظه است (یک mutex نقش transaction را بازی می‌کند) و NATS توکار است. عددهای ترافیک فرضی‌اند، بارها seed دارند، شمارش چاپ می‌کنم نه زمان.

## case ۱: rate limiter به عنوان سرویس

نیازمندی (فرضی): ۵ میلیون کاربر روزانه، هر کدام ۳۰ check، اوج ۵ برابر؛ از کار افتادن limiter نباید API را بخواباند.

```
avg checks/s        1736
peak checks/s (x5)  8681
measured bytes/key  136 (map + 16-byte key + bucket, 1M keys)
5M active keys      0.68 GB of state
```

| بخش | انتخاب |
|---|---|
| API | `POST /check {key, cost}` جواب `{allowed, remaining, retry_after_ms}` می‌دهد؛ API آن را به `X-RateLimit-Remaining` و `429` و `Retry-After` تبدیل می‌کند |
| الگوریتم‌ها | {{< term "token-bucket" "token bucket" >}} و {{< term "sliding-window" "sliding window counter" >}} پشت یک interface |
| state | به‌ازای هر key، در حافظه، shard شده روی نودها با {{< term "consistent-hashing" "consistent hashing" >}} |
| کلاینت | {{< term "deadline" "deadline" >}} برای هر درخواست، بعد {{< term "fail-open" "fail open" >}} به یک bucket محلی |

یک key با ۳۰۰ درخواست در ثانیه به مدت ۱۰ ثانیه، با سقف ۱۰۰ در ثانیه:

```
token bucket 100/s burst 100   offered 3018 allowed 1099 max in any 1s window 199
sliding window 100 per 1s      offered 3018 allowed 991 max in any 1s window 102
```

bucket روی نرخ یک burst هم اجازه می‌دهد (۱۹۹ در یک ثانیه)؛ window counter نرم‌تر ولی تقریبی است ([rate limiting توزیع‌شده](/fa/posts/ds-distributed-rate-limiting/)، [در Go](/fa/posts/go-rate-limiting-caching/)).

بعد ۱۰۰۰ key با ۲۰ درخواست در ثانیه در برابر سقف ۱۰، روی ۴ نود؛ `n4` در ثانیه‌ی ۵ حذف می‌شود:

```
keys that changed owner when n4 left: ring 288, hash mod N 731 (of 1000)
allowed, no failure 108202 | n4 removed at t=5s 110566 | extra 2364 (8.2 per moved key)
```

ring ([sharding](/fa/posts/ds-sharding-consistent-hashing/)) ۲۸۸ key را جابه‌جا می‌کند و mod N ‏۷۳۱ تا. key جابه‌جاشده با bucket پر شروع می‌کند، پس اضافه‌پذیرش حداکثر «key جابه‌جاشده ضرب burst» است: ۲۳۶۴ اضافه از ۲۰۰٬۶۷۶ درخواست. بعد یک {{< term "hot-key" "hot key" >}} با ۶۰٪ از ۲۰٬۰۰۰ check:

```
split=false checks per node n1..n4: 1930 1863 13878 2329 | hot key allowed 109
split=true  checks per node n1..n4: 4971 4863 4832 5334 | hot key allowed 108
```

چهار sub-key که هر کدام یک‌چهارم سقف را دارند بار را پخش می‌کنند. آخر، کلاینت و header‌ها روی HTTP در loopback، با bucketی که ساعتی یک token پر می‌شود (خروجی دقیق):

```
request 5: 200  X-RateLimit-Remaining=0 Retry-After=""
request 6: 429  X-RateLimit-Remaining=0 Retry-After="3600"
-- limiter stopped: client fails open to a local bucket (burst 2)
request 1: 200  X-RateLimit-Remaining=1 Retry-After=""
request 3: 429  X-RateLimit-Remaining=0 Retry-After="3600"
-- slow limiter (300 ms) with a 50 ms deadline: decision came from "local", fallbacks=1
```

شکست‌ها: گم شدن نود (اضافه‌پذیرش کوتاه)، limiter کند یا خراب (fail open با سقف bucket محلی؛ برای login من fail closed)، hot key (تقسیم). نساختم: gRPC و persistence.

## case ۲: سامانه‌ی اعلان

نیازمندی (فرضی): email و SMS و push؛ دو اولویت؛ ۳ میلیون در روز، اوج ۱۰ برابر؛ تماس با provider ‏۳۰۰ms؛ ۹۹٪ اولویت بالا ظرف ۱۰ ثانیه ارسال شود ([SLO](/fa/posts/eng-sli-slo-error-budgets/))؛ opt-out هنگام ارسال رعایت شود.

| بخش | انتخاب |
|---|---|
| API | `POST /notify {user, template, channels, priority, idempotency_key}`؛ validate، یک transaction برای اعلان و ردیف‌های outbox |
| relay | ردیف‌های outbox را با message id در {{< term "jetstream" "JetStream" >}} منتشر می‌کند ([outbox](/fa/posts/go-outbox-pattern-nats/)) |
| لاین‌ها | consumerهای `high` و `low`، اول `high` ({{< term "priority-lane" "priority lane" >}}) |
| worker | opt-out، quiet hours، سقف هر کاربر (کد case ۱)، breaker، ارسال، {{< term "dlq" "DLQ" >}} بعد از `MaxDeliver` |
| وضعیت | queued و sent و skipped و dead؛ «delivered» webhook می‌خواهد (نساختم) |

اجرا (در دو اجرا یکسان):

```
100 API calls, 40 distinct keys: notifications 40, deduped by key 60, rejected 0
relay published 80 rows; crash-and-republish sent 80 more, JetStream duplicate acks 80, stream holds 80
backlog: 200 low enqueued first, then 20 high; one worker
position of the last high-priority send: 20 (of 220)
200 emails, MaxDeliver 4, backoff 10/20/40 ms + jitter, provider: 30% 5xx, 10% timeout per attempt
sent on attempt 1/2/3/4: 131 / 45 / 15 / 5 | dead-lettered: 4 | provider calls: 302 (timeouts 25)
at 23:00 after alice opted out: statuses map[queued:1 sent:1 skipped:1], deferred (quiet hours, low priority) 1
10 push for one user, limit 20/s burst 3 (virtual clock): sent 10, limiter denials 80
1 campaign -> 10000 recipients: 20 batches of 500, limiter waits 18, virtual time 1.8 s
published 10000, stream holds 10000 messages, 1780000 bytes (178 bytes per message)
```

retry با {{< term "exponential-backoff" "exponential backoff" >}} و jitter است ([retry](/fa/posts/ds-timeouts-retries-backoff/)، [DLQ](/fa/posts/nats-jetstream-retry-dlq/)). ظرفیت: میانگین ۳۵ در ثانیه، اوج ۳۴۷، حدود ۱۰۴ تماس هم‌زمان ({{< term "littles-law" "قانون Little" >}})، و ۱٫۶ گیگابایت برای ۹ میلیون پیام ۱۷۸ بایتی. campaign یک فراخوانی و ۲۰ batch است.

مرور شکست‌ها:

| شکست | نتیجه در اجراهای من |
|---|---|
| provider خراب، بدون breaker | ۲۴۰ تماس، ۶۰ پیام به DLQ |
| provider خراب، با breaker (بعد از ۵ شکست باز می‌شود، هر دهمین تماس probe است) | ۲۸ تماس، ۶۰ پیام به DLQ ([breaker](/fa/posts/ds-circuit-breaker-bulkhead/)) |
| crash بعد از قبول provider و قبل از ثبت | ۴ از ۱۰۰ دوبار ارسال شد؛ با idempotency key‌ی provider صفر |
| crash بعد از ثبت و قبل از ack | ۹ redelivery را جدول sent خنثی کرد |
| crash‌ی relay بعد از publish | JetStream ردیف‌های دوباره‌منتشرشده را دور می‌ریزد |
| NATS خاموش | اجرا نکردم؛ ردیف‌ها در outbox می‌مانند |

ردیف اول crash همان لبه‌ی اجتناب‌ناپذیر {{< term "at-least-once-delivery" "at-least-once" >}} است ([idempotency](/fa/posts/nats-jetstream-idempotency/)): فقط کلید خود provider آن را می‌بندد. در اجرای breaker همه به DLQ می‌روند چون provider برنمی‌گردد؛ سامانه‌ی واقعی باید پارک کند. موفقیت ۹۸٫۰٪ شد، کمتر از هدف ۹۹٪؛ طبق تجربه‌ی من راهش provider دوم است، نه retry بیشتر. اگر پاسخ کند را «لاین high خالی» بخواند، ترتیب لاین‌ها می‌شکند.

## چند نکته‌ی مهم

- عددها شبیه‌سازی یا فرضی‌اند.
- fail open یا closed را پیش از حادثه انتخاب کنید.
- ترجیحات را هنگام ارسال بررسی کنید.
- تکرارها را در provider هم بشمارید.
- سن قدیمی‌ترین پیام را ببینید ([observability](/fa/posts/nats-jetstream-observability/)).

## تمرین

وضعیت `delivered` را با webhookهای شبیه‌سازی‌شده‌ی دیر یا تکراری یا گمشده اضافه کنید.

## قدم بعدی

«پروژه‌ی پایانی توزیع‌شده»، آخرین مقاله، قطعه‌ها را در یک پروژه کنار هم می‌گذارد.
