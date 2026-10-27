+++
date = '2027-06-09T10:00:00+03:30'
draft = false
title = 'روش‌های استقرار: blue-green و canary'
description = 'مقایسه‌ی روش‌های استقرار با اجرای Go روی loopback: big-bang، rolling، blue-green و canary با rollback خودکار، به‌همراه تغییر امن schema.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "deployment", "canary", "blue-green", "go"]
cover = { image = "/images/covers/ds-deployment-strategies.fa.png", alt = "روش‌های استقرار: blue-green و canary", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-modular-monolith-vs-microservices/) درباره‌ی تعداد قطعه‌های قابل استقرار بود. این یکی درباره‌ی این است که یک قطعه چطور به کاربر می‌رسد. هر deploy یک آزمایش روی production است؛ سؤال این است که پیش از فهمیدن، نسخه‌ی بد به چند کاربر آسیب می‌زند، یعنی {{< term "blast-radius" "blast radius" >}} آن. مرتبط: [طراحی pipeline](/fa/posts/eng-ci-cd-pipeline-design/) و [load balancer](/fa/posts/net-load-balancer-l4-l7/).

> صادقانه: این Go 1.26 روی یک ماشین و فقط loopback است. backendها سرورهای HTTP واقعی‌اند پشت یک reverse proxy وزن‌دار کوچک که خودم نوشتم (`httputil.ReverseProxy`). «باگ» v2 قطعی است: حدود ۵٪ شناسه‌ی درخواست‌ها 500 می‌گیرند. شمارش نشان می‌دهم، نه زمان.

## big-bang و rolling

big-bang همه چیز را یک‌باره عوض می‌کند. ۱۰٬۰۰۰ درخواست، همه از v2:

```
big-bang, 5% bug     requests=10000 errors=502 | v2: 10000 req 502 err
```

{{< term "rolling-update" "rolling update" >}} چهار instance را یکی‌یکی، بعد از هر ۲۰۰۰ درخواست، عوض می‌کند، به شرط اینکه جدید {{< term "health-check" "readiness check" >}} را رد کند. دو نسخه‌ی بد:

```
rolling, v2 fails readiness           requests=10000 errors=0   | v1: 10000 req
rolling, v2 5% bug passes readiness   requests=10000 errors=244 | v1: 5000 req 0 err | v2: 5000 req 244 err
```

اگر v2 بالا نیاید rollout متوقف می‌شود و کاربر چیزی نمی‌فهمد. ولی readiness فقط می‌پرسد «زنده‌ای؟». باگ ظریف از آن رد شد و نیمی از درخواست‌ها به v2 رسیدند. rolling از crash محافظت می‌کند، نه از رفتار غلط.

## blue-green

{{< term "blue-green-deployment" "blue-green" >}} ناوگان قدیمی (blue) را نگه می‌دارد و یک ناوگان کامل جدید (green) بالا می‌آورد؛ proxy ۱۰۰٪ را یک‌باره می‌چرخاند.

```
servers running during the switch: 4 (normal: 2)
smoke test on green: 20 requests, 1 errors -> flip
alarm rule: 10 errors seen -> after 152 requests (10 errors); flip back
after rollback (next 1000)   requests=1000 errors=0 | v1: 1000 req 0 err
```

هزینه، ظرفیت دوبرابر است: اینجا ۴ سرور به‌جای ۲. {{< term "smoke-test" "smoke test" >}} یک خطا در ۲۰ دید و گذراند، چون ۲۰ درخواست برای باگ ۵٪ کم است. فایده: rollback یک جابه‌جایی atomic است، فوری و بدون deploy دوباره.

درخواست‌های در حال انجام مراقبت می‌خواهند. ۵ درخواست کند روی blue شروع کردم، سوییچ کردم و blue را با {{< term "graceful-shutdown" "graceful shutdown" >}} بستم (مثل [این مقاله](/fa/posts/go-graceful-shutdown-workers/)):

```
during drain: in-flight on blue=5, new request -> v2 status 200
in-flight results (200 = finished, 0 = lost): [200 200 200 200 200], Shutdown error: <nil>
```

ترافیک تازه به green رفت و هر ۵ درخواست قدیمی تمام شدند.

## canary با تحلیل خودکار

{{< term "canary-release" "canary" >}} مرحله‌به‌مرحله ۱٪، ۵٪، ۲۵٪، ۵۰٪، ۱۰۰٪ بزرگ می‌شود. بعد از هر مرحله‌ی ۲۰۰۰ درخواستی، کد canary و baseline را با {{< term "fisher-exact-test" "آزمون دقیق Fisher" >}} یک‌طرفه مقایسه می‌کند؛ اگر p < 0.005 شد rollback می‌کند (آستانه را خودم انتخاب کردم). Fisher را به z-test ترجیح دادم چون با چند خطای معدود تقریب نرمال ضعیف است.

```
bad v2
step 1: weight=  1% canary n=  28 err= 0 | baseline n=1972 err=0 | p=1.0000 power(5% bug)=0.41 -> continue
step 2: weight=  5% canary n= 102 err= 5 | baseline n=1898 err=0 | p=0.0000 power(5% bug)=0.97 -> ROLLBACK
blast radius: 130 requests served by v2 (big-bang: 10000)
good v2
... step 4: weight= 50% canary n=1008 err=0 ... -> continue
step 5: weight=100% canary n=2000 err=0 -> PROMOTED
```

نسخه‌ی بد در مرحله‌ی ۲ با blast radius برابر ۱۳۰ درخواست متوقف شد، نه ۱۰٬۰۰۰. مرحله‌ی ۱ نکته را نشان می‌دهد: آزمون با ۲۸ درخواست canary گفت «اشکالی نیست». این شاهد سلامت نیست، {{< term "statistical-power" "توان آماری" >}} پایین است. کد آن را حساب می‌کند: با ۲۰ درخواست canary از ۲۰۰۰، احتمال تشخیص نرخ خطای واقعی ۵٪ برابر ۰٫۲۶ است و یک خطا در ۲۰ فقط p = 0.01 می‌دهد، که کافی نیست. حدود ۵۹ درخواست canary توان ۸۰٪ می‌دهد. (مسیریابی با hash است، پس مرحله‌ی ۱ عدد ۲۸ گرفت نه ۲۰.) فرض‌ها: baseline هیچ‌وقت خطا ندارد؛ برای چندبار نگاه کردن تصحیحی نکردم؛ فقط بررسی نرخ خطا را ساختم، نه latency.

## ترافیک سایه و feature flag

{{< term "shadow-mode" "shadow mode" >}} یک نسخه‌ی کپی از هر درخواست را به v2 می‌فرستد و فقط پاسخ‌ها را مقایسه می‌کند. ۲۰۰۰ درخواست mirror شده: ۰ خطای قابل‌دیدن برای کاربر و ۱۰۲ پاسخ متفاوت (اولی در درخواست ۱۲). بعد {{< term "feature-flag" "feature flag" >}} deploy را از release جدا می‌کند: کد را خاموش بفرستید، برای گروه‌ها روشن کنید و بدون deploy خاموش کنید ({{< term "kill-switch" "kill switch" >}}).

## تغییر دیتابیس

در همه‌ی روش‌های بالا نسخه‌ی قدیم و جدید هم‌پوشانی دارند، پس schema باید برای هر دو کار کند. این شبیه‌سازی با map است، نه Postgres؛ مراحل SQL همان مراحل معمول است و اجرایشان نکردم.

```
WRONG: rename in one step while v1 is still running
  first error: column "name" does not exist
  v1 reads name      ok=0 errors=100
RIGHT: expand, dual-write, backfill, switch reads, contract
  1 expand (v1 live)                    name: ok=100
  2 v1 and v2 both live, v2 dual-writes name: ok=110 | full_name: ok=5 empty=105
  3 backfill done (105 rows)            name: ok=110 | full_name: ok=110
  4 reads switched to full_name         full_name: ok=110
  5 contract (drop name, later release) full_name: ok=110
```

این همان {{< term "expand-contract" "expand/contract" >}} است: ستون را اضافه کن، {{< term "dual-write" "dual-write" >}} کن، {{< term "backfill" "backfill" >}} کن، خواندن را عوض کن و بعداً حذف کن. مصرف‌کننده‌ها {{< term "tolerant-reader" "tolerant reader" >}} باشند. ببینید [migration بدون downtime](/fa/posts/db-zero-downtime-migrations/).

## rollback یا roll-forward؟

به تجربه‌ی من تا وقتی rollback ارزان و امن است، حرکت اول است؛ و {{< term "roll-forward" "roll-forward" >}} وقتی برنده می‌شود که v2 داده‌ای نوشته که v1 نمی‌خواند یا migration چیزی را حذف کرده. {{< term "sli" "SLIها" >}}ی [SLO](/fa/posts/eng-sli-slo-error-budgets/) را به تفکیک نسخه ببینید، وگرنه canary ۱٪ در نویز گم می‌شود. Argo Rollouts، Flagger، Spinnaker و استراتژی‌های Deployment در Kubernetes این کار را خودکار می‌کنند؛ آن‌ها را فقط از مستندات می‌شناسم.

## چند نکته‌ی مهم

- readiness دلیل درستی نیست؛ rollout به metric واقعی نیاز دارد.
- canaryهای کوچک کورند: حجم نمونه‌ی لازم را حساب کنید.
- هر migration را پیش از کدی که به آن نیاز دارد backward compatible کنید.
- نوشتن‌های mirror شده نباید اثر جانبی داشته باشند.

## تمرین

به تحلیل canary یک بررسی latency با ساعت شمارشی اضافه کنید، بعد باگی بسازید که فقط ۰٫۵٪ درخواست‌ها را می‌گیرد و ببینید چند درخواست لازم است.

## قدم بعدی

مقاله‌ی بعد «برآورد ظرفیت» است.
