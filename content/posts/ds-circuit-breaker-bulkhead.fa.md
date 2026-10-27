+++
date = '2027-05-08T10:00:00+03:30'
draft = false
title = 'circuit breaker و bulkhead'
description = 'ساخت circuit breaker در Go از صفر با ساعت تزریق‌شده، به‌همراه bulkhead و load shedding، با شبیه‌سازی‌های seed ثابت و شمارش‌های واقعی.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "circuit-breaker", "bulkhead", "resilience", "go"]
cover = { image = "/images/covers/ds-circuit-breaker-bulkhead.fa.png", alt = "circuit breaker و bulkhead", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-timeouts-retries-backoff/) با retryهایی تمام شد که مؤدبانه صبر می‌کنند. وقتی وابستگی بیمار می‌ماند ادب کمکی نمی‌کند: callerها پشتش جمع می‌شوند تا خودشان هم بیمار شوند و {{< term "cascading-failure" "خرابی زنجیره‌ای" >}} رخ می‌دهد. {{< term "circuit-breaker" "circuit breaker" >}} مدتی صدا زدن را متوقف می‌کند و {{< term "bulkhead" "bulkhead" >}} سقف می‌گذارد که یک وابستگی چقدر از ظرفیت شما را بگیرد. ببینید: [الگوهای concurrency](/fa/posts/go-concurrency-patterns/).

> صادقانه: همه‌ی این‌ها Go 1.26 روی یک ماشین است. زمان «tick» ساختگی از یک ساعت تزریق‌شده است، randomness با seed ثابت است و فقط شمارش نشان می‌دهم، نه زمان. **شبیه‌سازی** است، نه شبکه‌ی واقعی.

## state machine

حالت closed درخواست‌ها را می‌گذراند و شکست‌های پشت‌سرهم را می‌شمارد. به آستانه که برسد open می‌شود و فوراً رد می‌کند. بعد از `OpenFor` tick به half-open می‌رود و چند درخواست آزمایشی (probe) را می‌گذراند: موفقیت آن را می‌بندد، یک شکست دوباره باز می‌کند با timer تازه. ساعت یک `func() int64` است، پس تست‌ها هیچ‌وقت sleep نمی‌کنند. table-driven هستند و با `go test -race` پاس می‌شوند.

```go
func (b *Breaker) Allow() bool   // false means fail fast
func (b *Breaker) Record(ok bool)
```

یک اجرای سناریودار (آستانه ۳، open برای ۱۰ tick، یک probe، وابستگی تا tick ۲۴ خراب):

```
  tick   4  closed    -> open
  tick  14  open      -> half-open
  tick  14  half-open -> open
  tick  24  open      -> half-open
  tick  24  half-open -> open
  tick  34  open      -> half-open
  tick  34  half-open -> closed
  trips=3 rejected=12
```

فقط شکست‌های پشت‌سرهم را پیاده کردم. نرخ شکست روی پنجره‌ی لغزان قاعده‌ی رایج دیگر است؛ آن را نساخته‌ام.

## چرا لازم است

۵ درخواست در هر tick در ۱۲۰ tick؛ وابستگی در tickهای ۲۰ تا ۷۹ کند است. هر درخواست در حال انجام یک goroutine پارک‌شده است. timeout کلاینت برابر ۱۰ tick تماس کند را شکست‌خورده تمام می‌کند.

```
  no breaker, no timeout       reached-dependency=600 ok=295 failed=300 fallback=  0 | in-flight peak=150 mean=77.5, goroutines peak=150, trips=0
  no breaker, timeout 10       reached-dependency=600 ok=295 failed=300 fallback=  0 | in-flight peak= 50 mean=27.5, goroutines peak= 50, trips=0
  breaker, timeout 10          reached-dependency=273 ok=216 failed= 52 fallback=327 | in-flight peak= 50 mean=6.2, goroutines peak= 50, trips=3
```

بدون هیچ سقفی کار در حال انجام با کندی بالا می‌رود. timeout آن را محدود می‌کند. breaker همان peak را دارد، چون فقط بعد از اولین timeoutها می‌فهمد، ولی میانگین از ۲۷٫۵ به ۶٫۲ می‌رسد و ۳۲۷ درخواست بدون رسیدن به وابستگی fallback گرفتند (پاسخ cache یا پیش‌فرض). بهایش okهای کمتر است (۲۱۶ در برابر ۲۹۵): breaker وقتی وابستگی سالم شده بود هم تا موفقیت probe بعضی تماس‌ها را رد کرد. شبیه‌سازی بهبود سریع‌تر وابستگی در اثر سبک شدن بار را مدل نمی‌کند؛ آن را اندازه نگرفتم.

## bulkhead و load shedding

A کند است (۳۰ tick برای هر تماس، ۲ درخواست در tick) و B سالم (۱ tick، ۳ در tick). B ۳۰۰ درخواست دارد. کلاینت‌ها بعد از ۱۰ tick انتظار منصرف می‌شوند. {{< term "load-shedding" "Shedding" >}} یعنی pool پر فوراً 503 یا 429 می‌دهد.

```
  shared 20, unbounded queue         B: ok= 27 shed=  0 gave-up=240 | A: ok= 79 shed=  0 gave-up=100 | max queue=149
  shared 20, shed at once            B: ok= 26 shed=274 gave-up=  0 | A: ok= 80 shed=120 gave-up=  0 | max queue=0
  shared 20, queue limit 10          B: ok= 80 shed=201 gave-up= 15 | A: ok= 74 shed=105 gave-up= 15 | max queue=10
  separate 10 + 10, shed at once     B: ok=300 shed=  0 gave-up=  0 | A: ok= 40 shed=160 gave-up=  0 | max queue=0
```

در pool مشترک تماس‌های کند A همه‌ی workerها را نگه می‌دارند و B گرسنه می‌ماند. shedding این را درست نمی‌کند، فقط سریع شکست می‌دهد. pool جدا ({{< term "semaphore" "semaphore" >}} برای هر وابستگی در Go) هر ۳۰۰ درخواست B را موفق می‌کند و A ضررش را خودش می‌کشد. صف بی‌حد بدترین است: ۲۴۰ درخواست B منتظر ماندند و رها شدند و کار باز هم برای هیچ‌کس انجام شد. این یعنی نبودن {{< term "backpressure" "backpressure" >}}.

## breaker و retry

دو ترتیب، ۳ تلاش، آستانه ۵، ۲۰۰ درخواست، یکی در هر tick. «داخل» یعنی هر تلاش از breaker می‌پرسد؛ «بیرون» یعنی breaker برای هر درخواست یک نتیجه می‌بیند.

```
  dependency down, retry inside      dependency calls= 14 ok requests=  0 fast-fails=199 trips=10
  dependency down, breaker outside   dependency calls= 42 ok requests=  0 fast-fails=186 trips=10
  flaky 60%, retry inside            dependency calls=169 ok requests= 74 fast-fails=113 trips=6
  flaky 60%, breaker outside         dependency calls=380 ok requests=161 fast-fails=  0 trips=0
```

وقتی وابستگی مرده است، «داخل» ارزان‌تر است (۱۴ تماس در برابر ۴۲)، چون retry روی breaker باز شکست رایگان است. وقتی فقط ناپایدار است، «داخل» با نویز عادی trip می‌کند و ۱۱۳ درخواست را برگرداند، در حالی که «بیرون» با ۱۶۱ ok و ۳۸۰ تماس تحملش کرد. به تجربه‌ی من برای وابستگی ناپایدارِ ولی مفید breaker را بیرون می‌گذارم و روی `ErrOpen` هرگز retry نمی‌کنم. در هر دو حالت retry به تماس {{< term "idempotency" "idempotent" >}} نیاز دارد.

## چه چیزی emit کنیم

metricها: state (یک gauge)، تعداد trip، تعداد رد شدن و fallbackهای داده‌شده. به تجربه‌ی من روی «بیش از N دقیقه open» و نرخ رد شدن alert بگذارید، نه روی هر trip. breakerی که بین open و half-open نوسان می‌کند نشانه‌ی {{< term "gray-failure" "gray failure" >}} است.

در production از کتابخانه استفاده می‌کنم. طبق README، `sony/gobreaker` حالت‌های closed، open و half-open، `MaxRequests` برای half-open، `Timeout` برای open، تابع `ReadyToTrip` و hook به نام `OnStateChange` دارد. README را خواندم و اجرایش نکردم. Hystrix و Resilience4j تا جایی که می‌دانم جایی هستند که این الگو در دنیای Java رایج شد.

## چند نکته‌ی مهم

- breaker حتماً fallback یا خطای روشن داشته باشد، وگرنه کاربر فقط شکست سریع‌تر می‌بیند.
- timeout کلاینت همچنان لازم است؛ breaker فقط بعد از دیدن شکست‌ها باز می‌شود.
- فقط شکست واقعی وابستگی را بشمارید، نه خطای validation خودتان را.
- اندازه‌ی pool و آستانه‌ها به load test نیاز دارند؛ اعداد من ساختگی‌اند.

## تمرین

یک قاعده‌ی نرخ شکست روی پنجره‌ی لغزان اضافه کنید و روی سناریوی ناپایدار با قاعده‌ی شکست‌های پشت‌سرهم مقایسه کنید.

## قدم بعدی

مقاله‌ی بعد «replication و quorum» است.
