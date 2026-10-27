+++
date = '2027-04-15T10:00:00+03:30'
draft = false
title = 'چرا سیستم توزیع‌شده سخت است'
description = 'چرا سیستم توزیع‌شده سخت است: خرابی جزئی، retry، اختلاف ساعت و گره‌ی کند، با شبیه‌سازی‌های Go با seed ثابت و یک دموی واقعی روی loopback.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "go", "partial-failure", "clocks", "failure-detection"]
cover = { image = "/images/covers/ds-why-distributed-is-hard.fa.png", alt = "چرا سیستم توزیع‌شده سخت است", hiddenInSingle = true }
+++

این اولین مقاله‌ی یک سری تازه درباره‌ی سیستم‌های توزیع‌شده است. سال‌هاست با queue، replica و RPC کار می‌کنم و بدترین باگ‌هایم از چند واقعیت تکراری آمده‌اند، پس بهتر است از نام‌گذاری همین‌ها شروع کنم. مقاله‌های قبلی از یک سو به این موضوع‌ها رسیده‌اند: [idempotency در JetStream](/fa/posts/nats-jetstream-idempotency/)، [الگوی outbox](/fa/posts/go-outbox-pattern-nats/) و [replication](/fa/posts/db-replication-streaming/). اینجا نقشه‌ی کلی است.

> صادقانه: بخش‌های ۱، ۲، ۴ و ۶ **شبیه‌سازی** هستند، در یک process و با تصادف seed‌دار (Go 1.26). شبکه‌ی شبیه‌سازی‌شده شبکه‌ی واقعی نیست؛ عددها شکل مسئله را نشان می‌دهند، نه نرخ‌های production. بخش ۵ process و TCP واقعی دارد ولی فقط روی loopback. فقط تعداد نشان می‌دهم، نه زمان.

## ۱. خرابی جزئی

در یک process یا فراخوانی برمی‌گردد یا برنامه می‌میرد. روی شبکه یک طرف می‌تواند خراب شود و طرف دیگر زنده بماند، پس فراخواننده باید حدس بزند. این همان {{< term "partial-failure" "خرابی جزئی" >}} (partial failure) است. `Withdraw(10)` شبیه‌سازی‌شده در ۱۰۰۰ فراخوانی با seed ثابت (۸٪ درخواست گم، ۴٪ crash سرور قبل از اعمال، ۱۵٪ پاسخ گم، ۲٪ درخواست تکراری):

```
outcome                          count  client sees   money moved
ok                                 702  reply         yes
request lost                        86  timeout       no
server crashed before applying      33  timeout       no
reply lost after applying          179  timeout       yes

timeouts: 298, requests applied by server: 897, replies received: 702
balance mismatch: client believes 7020 withdrawn, server withdrew 8970
```

سه واقعیت متفاوت یک «timeout» یکسان می‌سازند. کلاینت دو حالت اول (هیچ اتفاقی نیفتاده) را از سومی (اتفاق افتاده) تشخیص نمی‌دهد. نتیجه همین اختلاف موجودی است.

## ۲. retry بدون idempotency

راه‌حل بدیهی retry است. همان شبیه‌سازی، تا ۸ تلاش برای هر برداشت، یک بار بدون کلید و یک بار با کلید {{< term "idempotency" "idempotency" >}} (سرور کلیدهای اعمال‌شده را به یاد می‌آورد):

```
no key  : logical=1000 confirmed=1000 retries=338 server applied=1212 withdrawn=12120 expected=10000 extra=2120
with key: logical=1000 confirmed=1000 retries=338 server applied=1000 withdrawn=10000 expected=10000 extra=0
```

به همه‌ی کلاینت‌ها «موفق» گفته شد، ولی بدون کلید مشتری ۲۱۲۰ اضافه از دست داد. با کلید موجودی دقیق است. یک تست با `go test -race` بررسی می‌کند که فراخوان‌های هم‌زمان هیچ کلیدی را دوبار اعمال نمی‌کنند.

## ۳. مغالطه‌های معروف

فهرستی معروف به «مغالطه‌های محاسبات توزیع‌شده» هست (معمولاً به Peter Deutsch و همکاران در Sun نسبت داده می‌شود و نام James Gosling هم برای مورد هشتم می‌آید؛ در انتساب دقیق محتاطم). سری، هر ردیف را دوباره سراغ می‌رود:

| مغالطه | کجا آسیب می‌زند |
|---|---|
| شبکه قابل اعتماد است | بخش‌های ۱ و ۲ |
| تأخیر صفر است | بخش ۶ |
| پهنای باند نامحدود است | payload بزرگ، replication lag |
| شبکه امن است | اعتماد بین گره‌ها |
| توپولوژی عوض نمی‌شود | عضویت، failover |
| یک مدیر وجود دارد | ارتقا، نسخه‌ها |
| هزینه‌ی انتقال صفر است | serialization، APIهای پرحرف |
| شبکه همگن است | کلاینت‌ها و نسخه‌های مختلط |

## ۴. ساعت‌ها

`time.Now()` در Go هم قرائت دیواری دارد هم قرائت {{< term "monotonic-clock" "یکنوا" >}} (monotonic). شکل خروجی `String()` را با جایگزینی ارقام به `N` چاپ کردم:

```
has monotonic reading: true
NNNN-NN-NN NN:NN:NN.NNNNNN +NNNN +NNNN m=+N.NNNNNNNNN
has monotonic after Round(0): false
NNNN-NN-NN NN:NN:NN.NNNNNN +NNNN +NNNN
```

`Round(0)` بخش `m=` را حذف می‌کند و مدت‌زمان بین چنین مقدارهایی از ساعت دیواری حساب می‌شود. برای مدت‌زمان از ساعت یکنوا استفاده کنید. برای ترتیب رویدادها بین ماشین‌ها ساعت مشکل است: با {{< term "clock-skew" "اختلاف ساعت" >}} (clock skew) قاعده‌ی {{< term "last-write-wins" "last write wins" >}} می‌شکند. اختلاف‌های شبیه‌سازی‌شده: n1 صفر، n2 منفی ۳۰۰ میلی‌ثانیه، n3 مثبت ۵۰۰.

```
true t=1000ms  write x="A" via n1  stamp=1000
true t=1100ms  write x="B" via n2  stamp=800
after replication (keep highest stamp): x="A"  <- B was written later but lost
```

به همین دلیل در مقاله‌های بعد از ساعت منطقی صحبت می‌شود.

## ۵. یک خرابی واقعی روی loopback

دو process در Go روی TCP و `127.0.0.1`. سرور برداشت را اعمال می‌کند (یک فایل می‌نویسد) و ۳ ثانیه بعد پاسخ می‌دهد. پورت‌ها با `PORT` پنهان شده‌اند.

```
A) nobody listening:
client error: dial tcp 127.0.0.1:PORT: connect: connection refused
B) server SIGKILLed mid-call (after it applied the withdrawal):
client error: EOF
   balance file on the server side: 90
C) server frozen with SIGSTOP (alive but silent), client deadline 800 ms:
client error: read tcp 127.0.0.1:PORT->127.0.0.1:PORT: i/o timeout
```

سه پیام خطای واقعی. در B کلاینت فقط `EOF` دید ولی پول جابه‌جا شده بود. در C process زنده است ولی ساکت؛ {{< term "deadline" "deadline" >}} تنها نشانه است.

## ۶. هیچ‌وقت فقط crash نیست

{{< term "failure-detector" "تشخیص‌دهنده‌ی خرابی" >}} (failure detector) وقتی {{< term "heartbeat" "heartbeatها" >}} بیش از یک timeout قطع شوند گره را مشکوک می‌شمارد. شبیه‌سازی: ۶۰ ثانیه، heartbeat هر ۱۰۰ms، یک گره‌ی سالم، یک گره‌ی ۵ برابر کندتر و گره‌ای که در ثانیه‌ی ۳۰ می‌میرد:

```
timeout   healthy  slow(5x)  dead-node detection delay
  150 ms      24       120      66 ms
  250 ms       0        15     166 ms
  500 ms       0         0     416 ms
 1000 ms       0         0     916 ms
 2000 ms       0         0    1916 ms
requests with a 100 ms deadline that time out: healthy 2.1%, slow(5x) 52.5%
```

timeout کوتاه گره‌ی سالم را مشکوک می‌کند و بلند دیر مرگ را می‌فهمد. بدتر: در ۵۰۰ms گره‌ی کند هیچ‌وقت مشکوک نمی‌شود، ولی بیش از نیمی از درخواست‌هایش از deadline ۱۰۰ms رد می‌شوند. این {{< term "gray-failure" "خرابی خاکستری" >}} (gray failure) است؛ طبق تجربه‌ی من از crash تمیز سخت‌تر است.

## چند نکته‌ی مهم

- timeout یعنی «نامعلوم»، نه «شکست».
- retry بدون idempotency آسیب را چند برابر می‌کند.
- رویدادهای بین ماشین‌ها را با ساعت دیواری مرتب نکنید.
- سلامت با heartbeat یکی نیست.
- شبیه‌سازی شکل مسئله را یاد می‌دهد، جای تست واقعی را نمی‌گیرد.

## تمرین

seed و نرخ‌های گم‌شدن را در `pickFate` عوض کنید. آیا اختلاف موجودی خطی رشد می‌کند؟ بعد کلیدی بسازید که منقضی می‌شود و برگشت اعمال دوباره را ببینید.

## قدم بعدی

مقاله‌ی بعدی «CAP و PACELC درست» است.
