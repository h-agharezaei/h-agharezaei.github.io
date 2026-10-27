+++
date = '2027-06-08T10:00:00+03:30'
draft = false
title = 'modular monolith یا microservice؟'
description = 'modular monolith در برابر microservice با Go: یک ماژول را پشت HTTP می‌بریم و خطاهای تازه، hop، بایت و transaction ازدست‌رفته را می‌شماریم.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "microservices", "modular-monolith", "architecture", "go"]
cover = { image = "/images/covers/ds-modular-monolith-vs-microservices.fa.png", alt = "modular monolith یا microservice؟", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-fault-injection-testing/) به سیستم خطا تزریق کرد. این مقاله می‌پرسد آیا باید مرزهای شبکه‌ی بیشتری بسازیم تا خطا در آن‌ها تزریق شود. یک دامنه‌ی کوچک (orders و inventory و billing) را به شکل {{< term "modular-monolith" "modular monolith" >}} ساختم، بعد inventory را پشت HTTP بردم و شمردم چه عوض شد. پیش‌زمینه: [bounded context](/fa/posts/eng-ddd-basics/) و [ساختار پروژه](/fa/posts/go-project-layout-clean-architecture/).

> برچسب صادقانه: «سرویس» یک goroutine روی listener حلقه‌ی بازگشتی است، نه ماشین جدا. خطاهای شبکه از یک wrapper با seed ثابت می‌آید که خودم نوشتم (شبیه‌سازی)، و جدول latency هم شبیه‌سازی است. فقط شمارش، بدون زمان‌سنجی. قضاوت‌هایی که «طبق تجربه‌ی من» دارند نظر شخصی‌اند.

## مونولیت با مرزهای واقعی

هر ماژول یک package ریشه با interface باریک `Port` دارد؛ orders فقط `inventory.Port` و `billing.Port` را می‌بیند. یک تست importها را parse می‌کند و اگر ماژولی به internals ماژول دیگر import بدهد fail می‌شود:

```
$ go run ./cmd/archcheck .
ok: no module imports another module's internals
$ go run ./cmd/archcheck arch/testdata/bad
VIOLATION: orders/bad.go imports dsmod/modules/billing/internal/gateway
```

ثبت سفارش یک transaction دیتابیس روی orders و inventory و billing است. اگر پرداخت رد شود، ردیف سفارش و تغییر موجودی هر دو rollback می‌شوند (تست شده، با ۵۰ سفارش هم‌زمان و `go test -race`)؛ ببینید [ACID](/fa/posts/db-transactions-acid/).

## جداکردن inventory

همان `Port` حالا دو پیاده‌سازی دارد: درون‌process و یک client HTTP، با یک مقدار config انتخاب می‌شوند. `PlaceOrder` تغییر نکرد. یک {{< term "contract-test" "contract suite" >}} رفتاری (reserve، موجودی ناکافی، یک key دوبار، release) روی هر دو سبز است. سبزشدن suite بخش آسان است؛ بقیه‌ی مقاله آن چیزی است که suite پوشش نمی‌دهد.

## جداشدن چه هزینه‌ای دارد

**تکراری‌ها.** ۲۰۰۰ رزرو، هرکدام تا ۳ تلاش، با ۱۰٪ گم‌شدن request و ۱۰٪ گم‌شدن response:

```
key=false orders=2000 client-calls=2441 server-executions=2188 units-reserved=2188 extra=188
key=true  orders=2000 client-calls=2441 server-executions=2188 units-reserved=1999 extra=-1
```

بدون {{< term "idempotency" "idempotency key" >}} ۱۸۸ واحد دوبار رزرو شد. با key سرور تکراری‌زدایی می‌کند (۱۹۹۹: یک سفارش هیچ‌وقت نرسید). ببینید [timeout و retry](/fa/posts/ds-timeouts-retries-backoff/).

**transaction ازدست‌رفته.** ۱۰۰۰ سفارش، ۱۰٪ پرداخت ردشده:

```
monolith (one transaction)         confirmed=901 reserved-for-no-order=0
extracted, no net faults, naive    confirmed=901 reserved-for-no-order=99
extracted, 5%+5% faults, naive     confirmed=829 reserved-for-no-order=124
extracted, 5%+5% faults, saga+key  confirmed=900 reserved-for-no-order=0
```

حتی با شبکه‌ی کامل، رد پرداخت موجودی را بی‌دلیل نگه می‌دارد. یک release به عنوان {{< term "compensating-transaction" "compensation" >}} به‌علاوه‌ی retry اینجا درستش کرد: یک {{< term "saga" "saga" >}} کوچک ([saga و 2PC](/fa/posts/ds-saga-vs-2pc/)). کدی که مجبور شدم اضافه کنم.

**hop و بایت** برای یک سفارش ۵ خطی (بایت body درخواست و پاسخ):

```
batched  http-calls= 1 request-bytes= 127 response-bytes=  11
chatty   http-calls=10 request-bytes= 225 response-bytes= 160
in-process: http-calls=0 request-bytes=0 response-bytes=0
```

نسخه‌ی پرحرف (بررسی و رزرو برای هر خط) درون‌process دیده نمی‌شود و روی HTTP ده فراخوانی است.

**نسخه‌بندی.** سروری که `qty` را به `quantity` تغییر نام می‌دهد clientهای قدیمی را می‌شکند؛ فیلد تازه در پاسخ فقط client سخت‌گیر را می‌شکند:

```
server renamed qty->quantity, old client: inventory: status 400: json: unknown field "qty"
server added response field, tolerant client: <nil>
server added response field, strict client:   json: unknown field "warehouse"
```

{{< term "tolerant-reader" "tolerant reader" >}} باشید و تغییر نام را در دو گام انجام دهید (هر دو را بپذیر، بعد حذف کن).

**latency (شبیه‌سازی).** هر hop لگ‌نرمال با median برابر ۴۰ms و p99 برابر ۱۰۰ms (فرض خودم)، پشت‌سرهم، ۲۰۰۰۰۰ زنجیره:

```
hops=1 end-to-end p50=  39.9 ms p99= 100.0 ms p99/p50=2.50  chains with >=1 hop over its p99=1.0%
hops=3 end-to-end p50= 126.1 ms p99= 217.6 ms p99/p50=1.73  chains with >=1 hop over its p99=3.0%
hops=5 end-to-end p50= 212.5 ms p99= 326.1 ms p99/p50=1.53  chains with >=1 hop over its p99=4.9%
```

انتظار داشتم نسبت بزرگ شود؛ برای جمع، کوچک می‌شود چون hopهای کند مستقل همدیگر را میانگین می‌کنند. چیزی که بزرگ می‌شود {{< term "percentile" "p99" >}} مطلق و احتمال برخورد با یک hop کند است. جمع p99 هر hop (۵۰۰ms) زنجیره را بیش از حد تخمین می‌زند (۳۲۶ms). fan-out موازی به جای جمع، بیشینه می‌گیرد؛ شبیه‌سازی‌اش نکردم.

**سطح عملیاتی**، شمرده‌شده در demo من:

| | مونولیت | + سرویس inventory |
|---|---|---|
| واحد استقرار | ۱ | ۲ |
| health endpoint برای پایش | ۱ | ۲ |
| مقدار config تازه | ۰ | URL و timeout و retry |
| حالت‌های خرابی | مرگ process | همچنین timeout، پاسخ گم‌شده، تکراری |

[circuit breaker و bulkhead](/fa/posts/ds-circuit-breaker-bulkhead/) را هم به فهرست اضافه کنید.

## چه می‌خرید

استقرار مستقل، مقیاس جدا برای هر سرویس، تکنولوژی متفاوت و ایزوله‌سازی خرابی. {{< term "conways-law" "قانون کانوی" >}} می‌گوید ساختار از ارتباط پیروی می‌کند؛ پس وقتی سود دارد که چند تیم باید مستقل ship کنند، بار نامتوازن است یا نیاز قابلیت اطمینان فرق دارد. طبق تجربه‌ی من، تیم کوچک با مرزهای نامشخص به {{< term "distributed-monolith" "distributed monolith" >}} می‌رسد: استقرار قفل‌شده، دیتابیس مشترک، فراخوانی‌های پرحرف (تعداد فراخوانی در هر درخواست همان عددی است که باید دید).

## تصمیم و مسیر

تا جایی که یادم است «MonolithFirst» از Martin Fowler از شروع با مونولیت دفاع می‌کند؛ دیگران می‌گویند سرویس زودهنگام انضباط می‌آورد. نظر من: ماژولار شروع کنید، در درزی جدا کنید که با درد اثبات شده (مقیاس، تیم، قابلیت اطمینان)، به سرویس داده‌ی خودش را بدهید و هرگز دیتابیس را مشترک نکنید، و تدریجی بروید ([strangler](/fa/posts/eng-legacy-code/)).

## چند نکته‌ی مهم

- مرزها را با تست اجبار کنید، نه با حسن‌نیت.
- جداکردن، پیش از اولین درخواست idempotency key و timeout و compensation می‌خواهد.
- portها را درشت نگه دارید: یک فراخوانی برای هر use case.
- شبیه‌سازی شکل پدیده را نشان می‌دهد، نه عدد production.

## تمرین

`Release` را هم ۱۰٪ مواقع fail کنید و ببینید چند retry orphanها را روی صفر نگه می‌دارد.

## قدم بعدی

مقاله‌ی بعدی «روش‌های استقرار: blue-green و canary» است.
