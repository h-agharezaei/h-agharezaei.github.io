+++
date = '2027-06-12T10:00:00+03:30'
draft = false
title = 'پروژه‌ی پایانی توزیع‌شده'
description = 'پروژه‌ی پایانی سیستم توزیع‌شده: یک pipeline سفارش با retry، breaker، saga و رویداد، با invariant checker روی ۲۰۰ campaign تزریق خطا.'
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "capstone", "fault-injection", "saga", "go", "simulation"]
cover = { image = "/images/covers/ds-capstone.fa.png", alt = "پروژه‌ی پایانی توزیع‌شده", hiddenInSingle = true }
+++

مشتری روی «خرید» کلیک می‌کند. پشت این کلیک، سیستم باید موجودی را رزرو کند، کارت را شارژ کند و کالا را بفرستد، در حالی که سرویس پرداخت گاهی 503 می‌دهد، گاهی خیلی دیر جواب می‌دهد و گاهی بعد از اینکه پول را گرفته می‌میرد. در همین حال یکی از سرورهای خودمان وسط یک سفارش crash می‌کند و پیام‌هایی که صفحه‌ی سفارش را به‌روز می‌کنند گم می‌شوند یا دوبار می‌رسند. چه چیزی باید بسازیم تا در پایان، هر سفارش یا کاملاً انجام شده باشد یا کاملاً برگشته، و نه پولی گم شود و نه موجودی‌ای؟

این آخرین مقاله کل سری را در یک pipeline کوچک سفارش جمع می‌کند و دقیقاً همین سؤال را می‌آزماید. آزمون دو بخش دارد. اول یک checker که وضعیت نهایی را می‌خواند و فهرستی از قاعده‌ها را وارسی می‌کند، به سبک checker درستی (safety) که برای [Raft](/fa/posts/ds-consensus-raft/) داشتیم. دوم تعداد زیادی اجرای تصادفی ولی قابل‌تکرار با {{< term "fault-injection" "تزریق خطا" >}}، همان روشی که در [تست خرابی](/fa/posts/ds-fault-injection-testing/) دیدیم. در ۲۰۰ campaign و ۱۰٬۰۰۰ سفارش، checker هیچ نقضی پیدا نکرد.

این نتیجه فقط وقتی معنا دارد که checker بتواند شکست بخورد. برای همین هر مکانیزم را هم به‌نوبت خاموش می‌کنم و نشان می‌دهم checker آن‌وقت آسیب را می‌گیرد. این مقاله بعد از [case study: rate limiter و سامانه‌ی اعلان](/fa/posts/ds-case-studies/) می‌آید.

> دمو تا چه حد صادقانه است: اجرای اصلی با Go 1.26 بود و آن را روی یک Mac با Go 1.27 دوباره اجرا کردم. campaign با ۲۰۰ seed یک **شبیه‌سازی** است: event loop تک‌thread، ساعت مجازی، شبکه و message bus شبیه‌سازی‌شده، همه seed‌دار، و فقط شمارش. یک **اجرای زنده**‌ی جدا هم HTTP واقعی روی loopback و یک nats-server توکار واقعی دارد. topology ثابت است (بدون service registry) و همه‌چیز روی یک ماشین است. خروجی‌های زیر با خروجی‌های اجرای اصلی یکی است، به‌جز یک مورد که همان‌جا مشخص کرده‌ام.

## سیستم

یک سفارش از این گام‌ها می‌گذرد: رزرو موجودی، شارژ پرداخت، ارسال، و علامت‌زدن «کامل شد». اگر یک گام برای همیشه شکست بخورد، گام‌های قبلی برگردانده می‌شوند: شارژ لغو (refund) می‌شود، موجودی آزاد می‌شود و سفارش به حالت «جبران‌شده» (compensated) می‌رسد. هر گام در یک لاگ رویداد هم نوشته می‌شود. یک «مدل خواندن» (داده‌ای که صفحه‌ی سفارش نشان می‌دهد) از روی این لاگ و از راه یک message bus ساخته می‌شود.

جدول هر بخش را نشان می‌دهد، مکانیزمی که از آن محافظت می‌کند، و به زبان ساده آنچه انجام می‌دهد.

| بخش | مکانیزم | به زبان ساده |
|---|---|---|
| API | {{< term "idempotency-key" "کلید idempotency" >}} برای هر intent | مشتری‌ای که دوبار کلیک می‌کند یک «intent» را دوبار می‌فرستد. کلید به سیستم اجازه می‌دهد تکرار را بشناسد و فقط یک سفارش بسازد. |
| سرویس سفارش | لاگ رویداد همراه state، سبک {{< term "outbox-pattern" "outbox" >}} | state و رویدادها با هم نوشته می‌شوند، پس نه رویدادی گم می‌شود و نه رویدادی ساختگی می‌آید. |
| Orchestrator | {{< term "saga" "saga" >}} رزرو، پرداخت، ارسال؛ {{< term "compensating-transaction" "جبران" >}}؛ بعد از crash از لاگ ادامه می‌دهد | هماهنگ‌کننده‌ای که سفارش را از گام‌ها می‌گذراند، در شکست گام‌ها را برمی‌گرداند و بعد از crash با خواندن لاگ سفارش‌های نیمه‌کاره را ادامه می‌دهد. |
| پرداخت (HTTP) | timeout ۵۰ms، deadline ۶۰۰ms، {{< term "jitter" "jitter" >}}، {{< term "retry-budget" "retry budget" >}}، {{< term "circuit-breaker" "breaker" >}} | هر تلاش حداکثر ۵۰ms صبر می‌کند و کل یک فراخوانی حداکثر ۶۰۰ms. retryها زمان تصادفی صبر می‌کنند، به سهمی از ترافیک محدودند و تا وقتی breaker باز است کاملاً متوقف می‌شوند. |
| انبار | {{< term "optimistic-concurrency" "optimistic concurrency" >}} | دو سفارش برای یک کالا نمی‌توانند همدیگر را overwrite کنند: اگر نسخه از زمان خواندن عوض شده باشد، نوشتن شکست می‌خورد. |
| Bus و {{< term "read-model" "مدل خواندن" >}} | at-least-once، projection خودتوان | bus ممکن است پیام گم کند یا تکرار کند. projection (کدی که مدل خواندن را می‌سازد) پیامی را که قبلاً اعمال کرده نادیده می‌گیرد. |

حالا خطاها. هر seed ۵۰ intent را در ۵ موج می‌فرستد و یک‌چهارم آن‌ها دوبار ارسال می‌شوند. پرداخت در ۸٪ تلاش‌ها 503 جواب می‌دهد، در ۶٪ درخواست را اجرا می‌کند ولی دیر جواب می‌دهد، و در ۶٪ آن را اجرا می‌کند ولی پیش از جواب connection را reset می‌کند. جواب دیر و reset خطرناک‌ترین‌ها هستند: پول گرفته شده ولی فراخواننده نمی‌داند. علاوه بر این، پرداخت برای یک بازه‌ی ۵۰۰ms «blackhole» است (connection را می‌پذیرد و هرگز جواب نمی‌دهد). orchestrator وسط یک موج دو بار crash می‌کند و حافظه‌اش را از دست می‌دهد. و bus ۱۲٪ تحویل‌ها را گم می‌کند و ۱۲٪ دیگر را تکرار می‌کند.

## steady state

بعد از اینکه سیستم آرام شد (checker بعد از «quiescence» اجرا می‌شود، یعنی وقتی کاری باقی نمانده)، هفت ویژگی باید برقرار باشد. به آن‌ها invariant می‌گویند: چیزهایی که باید درست باشند، خطاها هر طور افتاده باشند.

- **I1** هر intent دقیقاً یک سفارش می‌دهد، در دقیقاً یک وضعیت پایانی، و هیچ سفارشی گیر نکرده است.
- **I2** حساب پول درست است: جمع شارژها منهای refundها برابر مبلغ سفارش‌های کامل‌شده است.
- **I3** موجودی هیچ‌وقت منفی نیست و برابر موجودی اولیه منهای تعداد سفارش‌های کامل‌شده است.
- **I4** مدل خواندن برابر چیزی است که با fold کردن (بازپخش) لاگ به دست می‌آید.
- **I5** هیچ سفارشی دوبار ارسال نمی‌شود.
- **I6** به‌طور میانگین حداکثر ۱٫۶ تلاش برای هر فراخوانی پرداخت.
- **I7** حداکثر ۸ retry در هر بازه‌ی ۲۵ میلی‌ثانیه‌ای، یعنی طوفان retry نداریم.

I1 تا I5 درستی‌اند. I6 و I7 درباره‌ی محافظت از سرویس پرداخت در برابر retryهای خودمان‌اند. سقف I6 و I7 انتخاب خودم است، نه استاندارد: عدد ۸ فقط بدترین مقداری است که با همه‌ی مکانیزم‌های روشن دیده شد.

## یک seed، بعد ۲۰۰ تا

اول یک seed، شماره‌ی ۷، تا خطاها را در کار ببینیم. دمو ردی از رویدادهای مهم چاپ می‌کند:

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

همه‌ی زمان‌ها میلی‌ثانیه‌ی مجازی‌اند. پنجره‌ی blackhole از ۸۲۵ms شروع می‌شود. پیش از آن، در ۳۸۰ms، orchestrator با ۲ سفارش نیمه‌کاره crash کرد و ۱۰۰ms بعد دوباره بالا آمد و آن‌ها را از لاگ ادامه داد. crash دوم، در ۱۰۷۴ms، ۱۰ سفارش نیمه‌کاره را گرفت و داخل پنجره‌ی blackhole افتاد. breaker در ۱۲۲۵ms بعد از یک شارژ ناموفق باز شد. در پایان: از ۵۰ سفارش، ۳۸ تا کامل شد و ۱۲ تا جبران (برگردانده) شد، ۳۸ تا ارسال شد و checker هیچ نقضی پیدا نکرد. ledger ۴۸ ردیف دارد، لاگ ۲۴۰ رویداد، و موجودی باقی‌مانده‌ی سه کالا ۳ و ۴ و ۷ است.

حالا همین را روی ۲۰۰ seed، در مجموع ۱۰٬۰۰۰ سفارش:

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

هر هفت invariant صفر نقض دارد. شمارش‌های زیر نتیجه نشان می‌دهند خطاها واقعاً رخ داده‌اند، و این مهم است: campaignای که هیچ چیزش خراب نشود چیزی را ثابت نمی‌کند. از ۱۰٬۰۰۰ سفارش، ۷٬۴۹۷ تا کامل و ۲٬۵۰۳ تا جبران شد (۷۸۶ تای آن‌ها به‌خاطر تمام‌شدن موجودی)، و هیچ‌کدام گیر نکرد. کلیدها ۱٬۵۱۷ تکرار پرداخت و ۲٬۴۹۹ تکرار API را جذب کردند، projection ۵٬۷۷۷ پیام تکراری را نادیده گرفت، و بعد از ۴۰۰ crash در orchestrator، ۲٬۷۱۴ سفارش از لاگ ادامه یافتند. breaker ۳۸۶ بار باز شد و budget ۶۹۱ retry را رد کرد.

## برداشتن مکانیزم‌ها

checkerی که می‌گذرد ممکن است checkerی باشد که هیچ‌وقت شکست نمی‌خورد. برای فهمیدن، هر مکانیزم را به‌نوبت خاموش می‌کنم و دوباره هر ۲۰۰ seed را اجرا می‌کنم. ستون‌ها: کدام invariantها شکستند، در چند seed از ۲۰۰ تا («bad»)، مجموع تلاش‌های پرداخت، چندتا از تلاش‌ها به سرویس blackhole خوردند، بدترین موج retry، و برای هر invariant شکسته نخستین seed ناموفق با تعداد seedهای ناموفق در پرانتز:

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

برای اینکه ببینیم نقض چه شکلی است، دمو برای یک seed ناموفق به‌ازای هر مکانیزم حرف خود checker را چاپ می‌کند، کنار همان seed با همه‌چیز روشن:

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

یک مقدار در این خروجی تغییر می‌کند: در مورد idempotency، checker اولین سفارشی را گزارش می‌کند که دوبار ارسال شده و آن را با پیمایش یک map پیدا می‌کند؛ برای همین در اجرای اصلی «order 16» چاپ شد و در بعضی اجراهای دوباره‌ی من «order 52». بقیه‌ی خروجی در اجرای دوباره دقیقاً یکسان بود.

هر شکست چه معنایی دارد:

- **بدون کلید idempotency** یک intent دو سفارش می‌سازد، ledger دیگر نمی‌خواند (۱٬۵۹۵ شارژ خالص در برابر ۱٬۴۳۰ برای سفارش‌های کامل‌شده، چون سفارش‌های تکراری و شارژهای تکرارشده دوباره اعمال می‌شوند) و یک سفارش دوبار ارسال می‌شود.
- **بدون جبران** سفارش ناموفق ناموفق می‌ماند: پول شارژشده می‌ماند (۱٬۲۳۰ با ۰ refund) و موجودی رزرو‌شده می‌ماند (موجودی ۲، در حالی که ۹ انتظار می‌رفت).
- **بدون بازیابی از لاگ** سفارشی که crash قطعش کرده وسط برگرداندن (وضعیت «cancel-charge») می‌ماند و هرگز تمام نمی‌شود.
- **بدون projection خودتوان** مدل خواندن پیام‌های تکراری را می‌شمارد، پس پولش (۱٬۳۳۰) از fold لاگ (۱٬۲۰۰) بیشتر است.
- **بدون optimistic concurrency** دو رزرو همدیگر را overwrite می‌کنند و موجودی غلط می‌شود (۲۹ به‌جای ۹).

سه ردیف وسط جدول با بقیه فرق دارند: retry budget و jitter و breaker از سرویس پرداخت محافظت می‌کنند، نه از درستی، و شاهد آن‌ها ضعیف‌تر است. بدون breaker تلاش‌هایی که به سرویس مرده می‌خورند سه برابر می‌شود (۲٬۶۹۶ به ۸٬۰۵۶)، ولی فقط ۲ seed از سقف I7 من رد می‌شوند. بدون budget یا بدون jitter فقط ۱ و ۵ seed رد می‌شوند. به تجربه‌ی من این‌ها زیر بار واقعی اهمیت پیدا می‌کنند، که این مدل ندارد.

## همان کد، socket واقعی

همه‌ی موارد بالا روی شبکه‌ی شبیه‌سازی‌شده اجرا شد. برای اینکه ببینیم شبیه‌سازی چیزی را پنهان نمی‌کند، همان کد orchestrator یک بار هم روی یک سرور پرداخت HTTP واقعی روی loopback اجرا شد، با خطاهایی که در یک `RoundTripper` جلوی آن تزریق می‌شوند (ساعت همچنان مجازی است)، و bus با یک nats-server توکار واقعی با JetStream جایگزین شد که روی یک port تصادفی و یک store موقت بالا آمد:

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

وضعیت نهایی اجرای زنده با اجرای شبیه‌سازی‌شده برابر است (`same final state: true`). سرور پرداخت فقط ۵۴ از ۷۸ تلاش را دید، چون خطاهایی مثل 503 تزریق‌شده یا blackhole هیچ‌وقت به سرور نمی‌رسند. روی bus، ۲۷۷ پیام برای لاگی با ۲۴۰ رویداد منتشر شد (تکراری‌ها)، ۲۹ تا بعد از nak دوباره تحویل شد، projection خودتوان ۳۷ تکرار را نادیده گرفت و بدون نقض تمام شد، و projection ساده I4 را شکست داد. `go test -race` سبز است، از جمله همین مقایسه.

## نقشه‌ی سری

هر بخش پروژه‌ی پایانی از یک مقاله‌ی قبلی می‌آید. این جدول می‌گوید از کدام، و چه چیزی داده است. دو موضوع، quorum و sharding، برای این سیستم لازم نبودند، و سه مقاله اینجا اجرا نشدند.

| مقاله | چه داد به پروژه |
|---|---|
| [چرا سیستم توزیع‌شده سخت است](/fa/posts/ds-why-distributed-is-hard/) | مدل خطا: پیام گم‌شده، دیر و تکراری، و crash |
| [CAP و PACELC درست](/fa/posts/ds-cap-pacelc/) | مدل خواندن ممکن است عقب بماند ولی همیشه خواندنی است: availability برای خواندن |
| [مدل‌های consistency](/fa/posts/ds-consistency-models/) | همگرایی نهایی مدل خواندن به لاگ |
| [ساعت منطقی: Lamport و vector clock](/fa/posts/ds-logical-clocks/) | شماره‌ی توالی روی رویدادها، نه زمان ساعت دیواری |
| [timeout، retry و backoff با jitter](/fa/posts/ds-timeouts-retries-backoff/) | deadline، jitter، retry budget |
| [circuit breaker و bulkhead](/fa/posts/ds-circuit-breaker-bulkhead/) | خود breaker |
| [replication و quorum](/fa/posts/ds-replication-quorum/) | ساخته نشد |
| [sharding و consistent hashing](/fa/posts/ds-sharding-consistent-hashing/) | ساخته نشد |
| [consensus و Raft](/fa/posts/ds-consensus-raft/) | سبک checker |
| [saga یا 2PC؟](/fa/posts/ds-saga-vs-2pc/) | orchestrator |
| [CQRS و event sourcing](/fa/posts/ds-cqrs-event-sourcing/) | لاگ و projection |
| [پیام‌رسانی و معماری رویدادمحور](/fa/posts/ds-messaging-event-driven/) | bus با at-least-once |
| [service discovery و load balancing](/fa/posts/ds-service-discovery-load-balancing/) | عمداً حذف شد: topology ثابت است |
| [rate limit توزیع‌شده](/fa/posts/ds-distributed-rate-limiting/) | هم‌خانواده‌ی retry budget |
| [تست خرابی با تزریق خطا](/fa/posts/ds-fault-injection-testing/) | برنامه‌ی خطای seed‌دار |
| [modular monolith یا microservice؟](/fa/posts/ds-modular-monolith-vs-microservices/) | اینجا یک process؛ فقط پرداخت در اجرای زنده پشت HTTP است |
| [روش‌های استقرار: blue-green و canary](/fa/posts/ds-deployment-strategies/) | اجرا نشد |
| [برآورد ظرفیت](/fa/posts/ds-capacity-estimation/) | اجرا نشد |
| [case study: rate limiter و سامانه‌ی اعلان](/fa/posts/ds-case-studies/) | عادت‌های طراحی |

## پوشش داده نشد

شبکه‌ی چندماشینه و partition واقعی، خرابی دیسک، سخت‌افزار ساعت، انواع Paxos، CRDT در عمق، geo-replication، امنیت mesh، اجرای Kubernetes.

## کجا ادامه بدهیم

مقاله‌ی Raft، کتاب «Designing Data-Intensive Applications» از Martin Kleppmann، تحلیل‌های Jepsen، «Distributed systems for fun and profit» و کتاب Google SRE. فقط نامشان را می‌آورم، نقل نمی‌کنم.

## حدود این نتیجه

- سقف‌های دیگر برای I6 و I7 جدول دیگری می‌دهد.
- صفر نقض در ۲۰۰ seed شاهد است، نه اثبات.
- انبار و ارسال داخل process هستند؛ bus لاگ تمام‌شده را بازپخش می‌کند.
- اجرای زنده فقط یک seed است.

## قدم بعدی

سری اینجا تمام می‌شود؛ ممنون که خواندید. سری‌های دیگر: Go، Rust، NATS، Git، Node.js، Databases، Algorithms، Networking، Python، Security، Engineering، Linux و Distributed Systems. مقاله‌های تازه می‌آیند، هر وقت چیز تازه‌ای یاد بگیرم.
