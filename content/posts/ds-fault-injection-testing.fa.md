+++
date = '2027-06-06T10:00:00+03:30'
draft = false
title = 'تست خرابی با تزریق خطا'
description = 'تست خرابی با تزریق خطا در Go: proxy خطازا و wrapper برای RoundTripper روی loopback، چهار باگ کلاینت را آشکار می‌کند و با seed ثابت بازتولید می‌شود.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "fault-injection", "chaos-engineering", "testing", "go"]
cover = { image = "/images/covers/ds-fault-injection-testing.fa.png", alt = "تست خرابی با تزریق خطا", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-distributed-rate-limiting/) درباره‌ی محدودیت‌ها بود. [timeout و retry](/fa/posts/ds-timeouts-retries-backoff/) و [circuit breaker](/fa/posts/ds-circuit-breaker-bulkhead/) کدی هستند برای روزی که یک وابستگی بد رفتار می‌کند، و کدی که در آن روز اجرا نشده باشد فقط حدس است. {{< term "fault-injection" "تزریق خطا" >}} آن روز بد را عمداً و ارزان می‌سازد. روش پیرامونش {{< term "chaos-engineering" "مهندسی آشوب" >}} است. مبانی تست: [تست در Go](/fa/posts/go-testing-basics/)، [تست JetStream](/fa/posts/nats-jetstream-testing/).

> صادقانه: همه‌چیز Go 1.26 روی loopback و یک ماشین است. proxy روی 127.0.0.1 یک **مدل** از شبکه‌ی بد است، نه خودِ آن. randomness با seed ثابت است و شمارش چاپ می‌کنم، نه زمان (ماشین شلوغ بود).

## طبقه‌بندی خطاها

تأخیر، خطا (5xx و 4xx)، reset یا refused شدن اتصال، hang، پاسخ ناقص، payload خراب، body کند، clock skew، تمام شدن منابع، kill شدن process. دموی من هفت مورد اول را پوشش می‌دهد؛ سه مورد آخر را نساخته‌ام.

## دو تزریق‌کننده

اول، یک proxy از نوع TCP بین کلاینت و سرور (ایده‌ی Toxiproxy که فقط اسمش را می‌شناسم و اجرایش نکرده‌ام). برای هر اتصال می‌تواند تأخیر با jitter بدهد، پهنای باند را محدود کند، بعد از N بایت ببندد، reset بفرستد، blackhole کند (بپذیرد، هرگز جواب ندهد)، 503 آماده بدهد، یا `drop_response`: درخواست را رد کند، بگذارد سرور تمام کند، بعد کلاینت را reset کند. دوم، یک wrapper برای `http.RoundTripper` در unit testهای بدون socket: error، 503، latency، truncate، corrupt.

برنامه‌ی خطا `Schedule{Seed, weights}` است؛ خطای اتصال `i` فقط به `(seed, i)` بستگی دارد. یک GET برای هر خطا، deadline ۳۰۰ms:

```
  pass           -> status 200, 100 body bytes, read: ok
  latency        -> status 200, 100 body bytes, read: ok
  bandwidth      -> deadline exceeded
  close_after    -> status 200, 13 body bytes, read: unexpected EOF
  reset          -> connection reset (or broken pipe)
  blackhole      -> deadline exceeded
  status503      -> status 503, 0 body bytes, read: ok
  drop_response  -> connection reset (or broken pipe)
```

`close_after` اول 200 و بعد body شکسته می‌دهد؛ `reset` گاهی broken pipe دیده شد، پس هر دو را یکی دسته‌بندی کردم.

## روش آزمایش

Principles of Chaos Engineering را این‌طور می‌فهمم: {{< term "steady-state" "steady state" >}} را به‌صورت یک متریک قابل‌اندازه‌گیری تعریف کن، فرض کن زیر خطا برقرار می‌ماند، تزریق کن، ببین، مقایسه کن و {{< term "blast-radius" "blast radius" >}} را کوچک نگه دار. اینجا steady state همان ایده‌ی SLO در [SLI، SLO و error budget](/fa/posts/eng-sli-slo-error-budgets/) است: دست‌کم ۹۹٪ از ۲۰۰ سفارش در {{< term "deadline" "deadline" >}} ۳۰۰ms موفق شوند.

فرضیه: با ۱۰٪ خطای 503 تزریق‌شده (seed برابر 7)، retry steady state را نگه می‌دارد.

```
  no retries                         ok=174/200 ( 87.0%) attempts=200
    steady state: VIOLATED
  3 attempts, no budget              ok=200/200 (100.0%) attempts=226
    steady state: HOLDS
  3 attempts, budget 20%, jitter     ok=198/200 ( 99.0%) attempts=224
    steady state: HOLDS
```

کلاینتِ budgetدار دقیقاً روی خط است. {{< term "retry-budget" "retry budget" >}} سقف retry را نسبتی از ترافیک می‌کند و {{< term "jitter" "jitter" >}} آن‌ها را پخش می‌کند.

## چهار باگی که پیدا می‌شود

**الف) retry بدون idempotency key.** خطا: پاسخ بعد از اعمال شارژ در سرور گم می‌شود (۱۵٪ `drop_response`، ۵٪ 503، ۱۰۰ سفارش).

```
  retry, no key (before)             ok=100/100 attempts=122 charges=118 double-charged=16
  retry + Idempotency-Key (after)    ok=100/100 attempts=122 charges=100 double-charged=0
```

همه‌ی سفارش‌ها «موفق» بودند، اما ۱۶ مشتری دو بار پرداخت کردند. نرخ موفقیت این را نشان نمی‌دهد؛ شمارش خودِ سرور هم باید بررسی شود. راه‌حل کلید {{< term "idempotency" "idempotency" >}} است.

**ب) بدون timeout.** خطا: blackhole. تست ۲ ثانیه منتظر می‌ماند:

```
  no timeout (before)        returned within 2s: false
  300ms deadline (after)     returned within 2s: true
```

**ج) retry storm.** upstream از کار افتاده، ۴۰ سفارش، ۵ تلاش. یک {{< term "retry-storm" "retry storm" >}} بار را روی چیزی که از قبل بیمار است چند برابر می‌کند:

```
  5 attempts, no budget (before)     upstream-hits=200 for 40 orders (x5.00 amplification)
  5 attempts, budget 10% (after)     upstream-hits= 43 for 40 orders (x1.07 amplification)
```

در هر دو حالت از قطعی نجات نمی‌یابیم؛ budget فقط جلوی بدتر کردن را می‌گیرد.

**د) {{< term "circuit-breaker" "circuit breaker" >}} که هرگز نمی‌بندد.** باگی که خودم گذاشتم: probe موفق در half-open مدار را نمی‌بندد. وابستگی در tickهای ۲۰ تا ۴۹ خراب است (tick ساختگی، wrapper داخل process):

```
  probe bug (before)   final state=half-open rejected= 94 ok in ticks 65..119:  0/55
  probe fixed (after)  final state=closed    rejected= 27 ok in ticks 65..119: 55/55
```

باگ breaker را خودم کاشتم؛ باگ‌های واقعی عجیب‌ترند. تست‌ها با `go test -race` پاس می‌شوند.

## بازتولید خطا با seed

seed یکسان، transcript یکسان (خطاها، نتیجه‌ی سفارش‌ها، شارژها). md5 transcript:

```
  seed 42, run 1: md5 1a6089762f2084ba9da0a3e6ab92b0b8
  seed 42, run 2: md5 1a6089762f2084ba9da0a3e6ab92b0b8
  seed 43, run 1: md5 3a1de6b1fe8c0b3e9b36d2e12f23983d
```

دو اجرای کامل برنامه خروجی یکسان داد. جاروب seedهای ۱ تا ۳۰ (۲۰ سفارش، ۳٪ پاسخ گمشده، بدون key) در ۱۴ seed شارژ دوباره دید و بازپخش seed 3 دو بار همان سفارش دوبارشارژشده (۴) را داد. یک {{< term "flaky-test" "شکست flaky" >}} قابل بازتولید شد. این فقط چون کلاینت پشت‌سرهم است جواب می‌دهد؛ هم‌زمانی ترتیب را عوض می‌کند.

گام بعد {{< term "deterministic-simulation" "شبیه‌سازی قطعی" >}} است که زمان و شبکه هم شبیه‌سازی می‌شوند؛ تا جایی که می‌دانم FoundationDB، TigerBeetle و Antithesis این‌طور کار می‌کنند. Jepsen با تزریق خطا [مدل‌های consistency](/fa/posts/ds-consistency-models/) را تست می‌کند. Chaos Monkey، LitmusChaos، Gremlin و AWS FIS برای زیرساخت واقعی‌اند؛ هیچ‌کدام را استفاده نکردم.

## کجا اجرا کنیم

در تجربه‌ی من: unit test با RoundTripper در CI برای هر commit، proxy در CI یا staging، و production فقط با حفاظ. یک {{< term "game-day" "game day" >}} به runbook، نقش‌های مشخص، شرط‌های توقف و کانال ارتباطی نیاز دارد. بدون این‌ها در production خطا تزریق نمی‌کنم.

## چند نکته‌ی مهم

- فرضیه را اول، با عدد، بنویسید.
- درستی (شارژ دوباره) را بسنجید، نه فقط دسترس‌پذیری را.
- blast radius را کوچک نگه دارید.
- شبکه‌ی شبیه‌سازی‌شده packet loss واقعی را ندارد.

## تمرین

یک خطای clock-skew به RoundTripper اضافه کنید (header ‏`Date` را جابه‌جا کنید) و کلاینتی را که به آن اعتماد می‌کند تست کنید.

## قدم بعدی

مقاله‌ی بعد «modular monolith یا microservice؟» است.
