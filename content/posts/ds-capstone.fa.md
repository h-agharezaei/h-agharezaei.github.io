+++
date = '2027-06-12T10:00:00+03:30'
draft = false
title = 'پروژه‌ی پایانی توزیع‌شده'
description = 'پروژه‌ی پایانی سیستم توزیع‌شده: یک pipeline سفارش با retry، breaker، saga و رویداد، با invariant checker روی ۲۰۰ campaign تزریق خطا.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "capstone", "fault-injection", "saga", "go", "simulation"]
cover = { image = "/images/covers/ds-capstone.fa.png", alt = "پروژه‌ی پایانی توزیع‌شده", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-case-studies/) دو طراحی را مرور کرد. حالا کل سری در یک pipeline سفارش جمع می‌شود و من با {{< term "fault-injection" "تزریق خطا" >}} و checkerی شبیه [Raft](/fa/posts/ds-consensus-raft/) می‌کوشم خرابش کنم.

> برچسب صادقانه: Go 1.26 روی یک Mac. campaign با ۲۰۰ seed یک **شبیه‌سازی** است (event loop تک‌thread، ساعت مجازی، شبکه و bus شبیه‌سازی‌شده، همه seed دار، فقط شمارش). یک **اجرای زنده**‌ی جدا هم HTTP واقعی روی loopback و nats-server توکار واقعی دارد. topology ثابت، بدون registry، یک ماشین.

## سیستم

| بخش | مکانیزم |
|---|---|
| API | {{< term "idempotency-key" "کلید idempotency" >}} برای هر intent |
| سرویس سفارش | لاگ رویداد همراه state، سبک {{< term "outbox-pattern" "outbox" >}} |
| Orchestrator | {{< term "saga" "saga" >}} رزرو، پرداخت، ارسال؛ {{< term "compensating-transaction" "جبران" >}}؛ بعد از crash از لاگ ادامه می‌دهد |
| پرداخت (HTTP) | timeout ۵۰ms، deadline ۶۰۰ms، {{< term "jitter" "jitter" >}}، {{< term "retry-budget" "retry budget" >}}، {{< term "circuit-breaker" "breaker" >}} |
| انبار | {{< term "optimistic-concurrency" "optimistic concurrency" >}} |
| Bus و {{< term "read-model" "مدل خواندن" >}} | at-least-once، projection خودتوان |

هر seed ۵۰ intent را در ۵ موج می‌فرستد و یک‌چهارم دوبار ارسال می‌شوند. پرداخت ۸٪ جواب 503 می‌دهد، ۶٪ اجرا می‌کند ولی دیر جواب می‌دهد، ۶٪ بعد از اجرا connection را reset می‌کند و ۵۰۰ms هم blackhole است. orchestrator دو بار وسط موج crash می‌کند. bus هر کدام ۱۲٪ پیام را drop و تکراری می‌کند.

## steady state

بعد از quiescence بررسی می‌شود:

- **I1** هر intent دقیقاً یک سفارش در یک حالت پایانی دارد، هیچ‌کدام گیر نکرده.
- **I2** شارژ منهای بازپرداخت برابر پول سفارش‌های کامل‌شده است.
- **I3** موجودی منفی نمی‌شود و برابر اولیه منهای تعداد کامل‌شده‌هاست.
- **I4** مدل خواندن برابر fold لاگ است.
- **I5** هیچ سفارشی دوبار ارسال نمی‌شود.
- **I6, I7** حداکثر ۱٫۶ attempt برای هر call و ۸ retry در ۲۵ms. این سقف‌ها انتخاب خودم است؛ ۸ بدترین مقدار با همه‌ی مکانیزم‌هاست.

## یک seed، بعد ۲۰۰ تا

```
seed 7: payment blackhole window t=825..1325 ms (virtual)
  t= 380  orchestrator CRASH, memory lost (flows, breaker, budget), 2 orders not yet terminal
  t= 480  orchestrator restarted, replaying the log: resuming 2 non-terminal orders
  t=1074  orchestrator CRASH, memory lost (flows, breaker, budget), 10 orders not yet terminal
  t=1174  orchestrator restarted, replaying the log: resuming 10 non-terminal orders
  t=1225  breaker OPEN after a failed charge (order 35)
  orders=50 completed=38 compensated=12 ledger=48 log=240 stock=[3 4 7] shipped=38
  violations: []
```

```
ALL MECHANISMS ON: 200 seeds x 50 intents (10000 orders)  seeds with a violation: 0
  I1 violations: 0
  I2 violations: 0
  I3 violations: 0
  I4 violations: 0
  I5 violations: 0
  I6 violations: 0
  I7 violations: 0
SLI counts over the campaign (no timings):
  orders completed=7497 compensated=2503 (out of stock=786) stuck=0
  payment calls=13252 attempts=15077 retries=3734 short-circuited=16265 retries denied by budget=691 breaker trips=386
  duplicates suppressed: api=2499 payment=1517 shipping=91 projection=5777
  bus: redelivered=6509 duplicated=5777 | inventory OCC conflicts=13340 | orchestrator crashes=400, orders resumed from log=2714
  attempts that hit the blackholed service=2696, worst retry wave (retries within 25 ms) in any seed=8
```

صفر نقض. کلیدها ۱۵۱۷ تکرار پرداخت و ۲۴۹۹ تکرار API را جذب کردند، projection ۵۷۷۷ تکراری را، و ۲۷۱۴ سفارش بعد از crash ادامه یافتند.

## برداشتن مکانیزم‌ها

checkerی که هیچ‌وقت هشدار نمی‌دهد شاید کور باشد، پس هر مکانیزم را به‌نوبت خاموش می‌کنم:

```
mechanism removed       broken    bad      attempts  blackhole wave  first failing seed per invariant: I:seed(count)
(nothing: all on)       -           0/200  15077     2696      8    
idempotency keys        I1,I2,I5  200/200  15975     2565      6     I1:1(200) I2:1(200) I5:1(67)
retry budget            I7          1/200  14999     2689      11    I7:174(1)
jitter                  I7          5/200  15034     2665      11    I7:73(5)
circuit breaker         I7          2/200  20580     8056      10    I7:44(2)
saga compensation       I1,I2,I3  200/200  12552     2547      6     I1:1(200) I2:1(187) I3:1(200)
log recovery            I1,I2,I3  198/200  11292     2090      6     I1:1(198) I2:1(182) I3:1(198)
idempotent projection   I4        200/200  15077     2696      8     I4:1(200)
optimistic concurrency  I3        200/200  16420     3063      7     I3:1(200)
```

```
without idempotency keys, seed 1:
  I1 intent 0 produced 2 orders
  I2 charged 1615 - refunded 20 = 1595, completed orders = 1430
  I5 order 16 shipped 2 times
  same seed, all on: 0 violations
without jitter, seed 73:
  I7 9 retries inside 25 ms (limit 8)
  same seed, all on: 0 violations
without circuit breaker, seed 44:
  I7 9 retries inside 25 ms (limit 8)
  same seed, all on: 0 violations
without saga compensation, seed 1:
  I1 order 19 ends in state "failed"
  I2 charged 1230 - refunded 0 = 1230, completed orders = 1200
  I3 sku 0 stock 2, expected 9
  same seed, all on: 0 violations
without log recovery, seed 1:
  I1 order 19 ends in state "cancel-charge"
  I2 charged 1105 - refunded 30 = 1075, completed orders = 1055
  I3 sku 0 stock 6, expected 11
  same seed, all on: 0 violations
without idempotent projection, seed 1:
  I4 read model money 1330 used [28 30 30], fold money 1200 used [23 26 29]
  same seed, all on: 0 violations
without optimistic concurrency, seed 1:
  I3 sku 0 stock 29, expected 9
  same seed, all on: 0 violations
```

بدون کلید، ledger و ارسال‌ها دوبرابر می‌شوند؛ بدون جبران، سفارش ناموفق موجودی و پول را نگه می‌دارد؛ بدون recovery سفارش‌ها گیر می‌کنند؛ projection ساده تکراری‌ها را می‌شمارد؛ بدون version رزروها همدیگر را بازنویسی می‌کنند.

سه مورد آخر از وابستگی محافظت می‌کنند و شواهدشان ضعیف‌تر است. بدون breaker تعداد attemptهایی که به سرویس مرده می‌خورند سه‌برابر می‌شود (۲۶۹۶ به ۸۰۵۶)، ولی فقط ۲ seed از سقف I7 رد می‌شوند؛ بدون budget یا jitter ۱ و ۵ seed. به تجربه‌ی من اهمیتشان زیر بار واقعی پیدا می‌شود که این مدل ندارد.

## همان کد، socket واقعی

```
live run, seed 7: payment service = real HTTP server on loopback behind a fault-injecting RoundTripper
  http requests served by the payment service: 54 (simulated run made 78 attempts)
  simulated: orders=50 completed=38 compensated=12 ledger=48 log=240 stock=[3 4 7] shipped=38
  live:      orders=50 completed=38 compensated=12 ledger=48 log=240 stock=[3 4 7] shipped=38
  same final state: true
  embedded nats-server with JetStream started (random port, temporary store)
  idempotent projection      published=277 (log has 240) acked=277 redelivered(nak)=29 duplicates suppressed=37 -> violations []
  non-idempotent projection  published=277 (log has 240) acked=277 redelivered(nak)=29 duplicates suppressed=0 -> violations [I4]
  nats-server stopped, store deleted: true
```

وضعیت نهایی با شبیه‌سازی یکی است؛ سرور ۵۴ از ۷۸ attempt را دید و بقیه 503 تزریقی و blackhole بودند. projection ساده I4 را می‌شکند. `go test -race` پاس می‌شود.

## نقشه‌ی سری

| مقاله | چه داد به پروژه |
|---|---|
| [چرا سخت است](/fa/posts/ds-why-distributed-is-hard/) | مدل خطا |
| [CAP](/fa/posts/ds-cap-pacelc/) | availability برای خواندن |
| [Consistency](/fa/posts/ds-consistency-models/) | همگرایی نهایی |
| [ساعت‌ها](/fa/posts/ds-logical-clocks/) | شماره‌ی توالی، نه زمان |
| [Retry](/fa/posts/ds-timeouts-retries-backoff/) | deadline، jitter، budget |
| [Breaker](/fa/posts/ds-circuit-breaker-bulkhead/) | خود breaker |
| [Quorum](/fa/posts/ds-replication-quorum/) | ساخته نشد |
| [Sharding](/fa/posts/ds-sharding-consistent-hashing/) | ساخته نشد |
| [Raft](/fa/posts/ds-consensus-raft/) | سبک checker |
| [Saga](/fa/posts/ds-saga-vs-2pc/) | orchestrator |
| [CQRS](/fa/posts/ds-cqrs-event-sourcing/) | لاگ و projection |
| [پیام‌رسانی](/fa/posts/ds-messaging-event-driven/) | bus at-least-once |
| [Discovery](/fa/posts/ds-service-discovery-load-balancing/) | عمداً حذف: ثابت |
| [Rate limit](/fa/posts/ds-distributed-rate-limiting/) | هم‌خانواده‌ی budget |
| [تزریق خطا](/fa/posts/ds-fault-injection-testing/) | برنامه‌ی خطای seed دار |
| [Monolith](/fa/posts/ds-modular-monolith-vs-microservices/) | اینجا یک process |
| [استقرار](/fa/posts/ds-deployment-strategies/) | اجرا نشد |
| [ظرفیت](/fa/posts/ds-capacity-estimation/) | اجرا نشد |
| [Case study](/fa/posts/ds-case-studies/) | عادت‌های طراحی |

## پوشش داده نشد

شبکه‌ی چندماشینه و partition واقعی، خرابی دیسک، سخت‌افزار ساعت، انواع Paxos، CRDT در عمق، geo-replication، امنیت mesh، اجرای Kubernetes.

## کجا ادامه بدهیم

مقاله‌ی Raft، کتاب «Designing Data-Intensive Applications» از Martin Kleppmann، تحلیل‌های Jepsen، «Distributed systems for fun and profit» و کتاب Google SRE. فقط نامشان را می‌آورم، نقل نمی‌کنم.

## چند نکته‌ی مهم

- سقف‌های دیگر برای I6 و I7 جدول دیگری می‌دهد.
- صفر نقض در ۲۰۰ seed شاهد است، نه اثبات.
- انبار و ارسال داخل process هستند؛ bus لاگ تمام‌شده را بازپخش می‌کند.
- اجرای زنده فقط یک seed است.

## تمرین

shipping درخواست را اجرا کند و بعد جوابش را خراب کند. با کلید روشن، invariantی می‌شکند؟ با خاموش؟

## قدم بعدی

سری اینجا تمام می‌شود؛ ممنون که خواندید. سری‌های دیگر: Go، Rust، NATS، Git، Node.js، Databases، Algorithms، Networking، Python، Security، Engineering، Linux و Distributed Systems. مقاله‌های تازه می‌آیند، هر وقت چیز تازه‌ای یاد بگیرم.
