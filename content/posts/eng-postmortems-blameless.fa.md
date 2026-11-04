+++
date = '2027-05-16T10:00:00+03:30'
draft = false
title = 'postmortem بدون سرزنش'
contentType = 'tutorial'
description = 'postmortem بدون سرزنش با یک حادثه‌ی ساختگی در Go: timeline از لاگ، TTD/TTM/TTR، عامل‌های مؤثر، action item و lint قابل اجرای سند.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["postmortem", "incident", "blameless", "software-engineering", "go", "slog"]
cover = { image = "/images/covers/eng-postmortems-blameless.fa.png", alt = "postmortem بدون سرزنش", hiddenInSingle = true }
+++

پایان یک جلسه‌ی بررسی حادثه را تصور کنید. سرویس مدتی از کار افتاده بود، علتش پیدا شده و یکی سؤال طبیعی را می‌پرسد: «خب، این تغییر را چه کسی deploy کرد؟» اسمی گفته می‌شود، همه سر تکان می‌دهند و جلسه تمام می‌شود. همه حس می‌کنند مشکل فهمیده شد. ماه بعد همان جور تغییری از دست آدم دیگری بیرون می‌آید و دقیقاً همان‌طور خراب می‌کند.

بررسی به یک آدم رسید، و آدم تنها جایی است که هیچ چیز را نمی‌شود در آن درست کرد. **postmortem بدون سرزنش** سؤال دیگری می‌پرسد: چه چیزی جلوی این را می‌گرفت؟ جواب تقریباً همیشه چیزی در خود سیستم است: یک بررسی که نبود، rolloutی که یک‌جا همه‌چیز را می‌گیرد، هشداری که فقط بعد از آسیب دیدن کاربر فعال می‌شود. {{< term "postmortem" "postmortem" >}} یعنی یک بررسی مکتوب از حادثه که از روی شواهد (لاگ و metric) ساخته می‌شود و یک timeline دارد، عامل‌هایی که به حادثه رسیدند و فهرستی از کارهای بعدی.

این مقاله ادامه‌ی مقاله‌ی قبل است، [SLI، SLO و error budget](/fa/posts/eng-sli-slo-error-budgets/): حادثه از {{< term "error-budget" "error budget" >}}ی خرج می‌کند که {{< term "slo" "SLO" >}} اجازه داده، و postmortem جایی است که تیم می‌نویسد این چه هزینه‌ای داشت و چه چیزی باید عوض شود. مطالب مرتبط: [پیکربندی، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/)، [connection pooling و شکست‌هایش](/fa/posts/db-connection-pooling/) و [طراحی pipeline برای CI/CD](/fa/posts/eng-ci-cd-pipeline-design/).

**حادثه‌ی این مقاله روی ماشین خودم ساختگی (staged) است.** کاربر واقعی و آدم واقعی در کار نیست و نام‌ها و نقش‌ها ساختگی‌اند. لاگ‌ها، عددها و خروجی lint از اجرای واقعی یک دموی کوچک Go آمده‌اند.

> دمو را دوباره با Go 1.27.3 اجرا کردم و `go test -race` سبز است (اجرای اول با Go 1.26 بود). «سرویس» یک مدل با زمان مجازی است: مولد تصادفی seed‌دار، ساعت تزریق‌شده، بدون socket و بدون sleep. برای همین timestampها در هر اجرا یکی‌اند.

## حادثه‌ی ساختگی

برای اینکه چیزی برای نوشتن داشته باشیم، دمو یک سرویس کوچک را شبیه‌سازی می‌کند. درخواست‌ها از یک connection pool می‌گذرند (تعداد ثابتی slot که هرکدام یک اتصال به دیتابیس یا یک وابستگی دیگر است). ماجرا به ترتیب این است:

1. ساعت 09:00:15 یک تغییر config سقف pool را از 10 به 2 می‌برد.
2. پنج ثانیه بعد وابستگی کند می‌شود: هر فراخوانی از 100 به 400 میلی‌ثانیه می‌رسد.
3. دو slot با 400 میلی‌ثانیه حدود 5 درخواست در ثانیه را جواب می‌دهند، ولی ترافیک حدود 10 در ثانیه است. درخواست‌ها برای گرفتن اتصال در صف می‌مانند و بعد از 1 ثانیه انتظار با خطا (HTTP 503) تسلیم می‌شوند.

سرویس {{< term "structured-logging" "لاگ ساختاریافته" >}} می‌نویسد: هر خط یک شیء JSON، با `slog` در Go. یک فایل شمارنده‌ی کوچک هم می‌نویسد. این‌ها یک خط خطای واقعی و شمارنده‌های پایانی‌اند:

```text
{"level":"ERROR","msg":"request","ts":"2027-05-10T09:00:22.304Z","id":209,"status":503,"wait_ms":1000,"dur_ms":0,"err":"pool wait timeout","pool_max":2}
requests_total{status="200"} 699
requests_total{status="503"} 201
```

هر درخواست ناموفق می‌گوید چه شد (`pool wait timeout`)، چقدر منتظر ماند (`wait_ms`: ‏1000) و pool آن لحظه چند slot داشت (`pool_max`: ‏2). این جزئیات بعداً مهم می‌شود، چون timeline فقط به اندازه‌ی لاگی که از آن ساخته می‌شود خوب است.

دو قاعده‌ی دیگر مدل: هشدار این است «نرخ خطا حداقل ۲۰٪ در ۱۰ ثانیه‌ی اخیر، با بررسی هر ۵ ثانیه». و mitigation (rollback کردن config) ۳۰ ثانیه بعد از فعال شدن هشدار انجام می‌شود. این تأخیر فرض من است، نه اندازه‌گیری از کسی.

## timeline از روی شواهد

اولین کار یک postmortem timeline است: چه اتفاقی، کی، به چه ترتیب. راه قابل‌اعتماد ساختنش از روی لاگ است، نه حافظه‌ی آدم‌ها. برنامه‌ی دوم دمو فقط `service.jsonl` را می‌خواند و لحظه‌های مهم را چاپ می‌کند. در خروجی‌اش `t+0:00` اولین درخواست ناموفق است و زمان‌های دیگر نسبت به آن‌اند:

```text
clock     t       event
09:00:15  t-0:07  deploy-pipeline applied cfg-1042 (pool_max=2)
09:00:22  t+0:00  first failed request (503, pool wait timeout)
09:00:30  t+0:07  alert fired: error rate >= 20% over 10s
09:01:00  t+0:37  oncall-engineer applied rollback-cfg-1042 (pool_max=10)
09:01:01  t+0:38  recovered: 20 healthy requests in a row

TTD (first error -> alert):      7.696s
TTM (first error -> mitigation): 37.696s
TTR (first error -> recovered):  38.957s
bad config live before first error: 7.304s
requests=900 failed=201 (22.3%)
assumed SLO 99.5% at 10 rps for 30 days: budget = 129600 failed requests; burned 0.16%
```

جدول از بالا به پایین خوانده می‌شود. اول تغییر config آمد (۷ ثانیه پیش از اولین خطا)، بعد اولین خطا، بعد هشدار، بعد rollback و بعد بازیابی. «بازیابی» یعنی اولین لحظه‌ی یک رشته‌ی ۲۰تایی از درخواست‌های سالم پشت سر هم بعد از rollback.

سه خط بعدی نشان می‌دهند تیم چطور عمل کرد، همه از شروع اثر شمرده می‌شوند:

- **TTD** (زمان تشخیص): از اولین خطا تا هشدار. فهمیدیم؟
- **TTM** (زمان مهار): از اولین خطا تا rollback. خونریزی را بستیم؟
- **TTR** (زمان بازیابی): از اولین خطا تا برگشتن ترافیک سالم. واقعاً تمام شد؟

عدد ۰٫۱۶٪ در انتها سهمی از error budget است که این حادثه خرج کرد: ۲۰۱ درخواست ناموفق از ۱۲۹٬۶۰۰ درخواست مجاز. این عدد فرض می‌کند ۱۰ درخواست در ثانیه در ۳۰ روز داریم، که برای دمو خودم ساختم. محاسبه‌ی واقعی ترافیک واقعی شما را لازم دارد.

## عامل‌های مؤثر، نه «علت اصلی»

نظر من: «علت اصلی» به‌صورت مفرد همه‌ی چیزهای دیگر را پنهان می‌کند. ببینید تست‌ها چه می‌گویند. وابستگی کند به تنهایی یک pool با اندازه‌ی ۱۰ را خراب نمی‌کند: با اندازه‌ی سالم، `TestHealthyConfigHasNoErrors` صفر خطا می‌بیند. اندازه‌ی بد pool هم به تنهایی خراب نمی‌کند: تست دوم با وابستگی سریع هم صفر خطا دارد، چون ۲ slot با ۱۰۰ میلی‌ثانیه حدود ۲۰ درخواست در ثانیه را جواب می‌دهند. هر دو با هم لازم بود.

چهار چیز با هم جور شدند:

- اندازه‌ی pool هیچ‌وقت validate نمی‌شد؛
- تغییر یک‌جا روی همه‌چیز رفت؛
- هیچ هشداری روی تأخیر وابستگی نبود؛
- تنها هشداری که داشتیم فقط خطا را می‌دید، پس وقتی فعال شد که کاربر آسیب دیده بود.

هرکدام یک {{< term "contributing-factor" "عامل مؤثر" >}} است و اصلاح خودش را دارد. یک {{< term "circuit-breaker" "circuit breaker" >}} هم ([circuit breaker و bulkhead](/fa/posts/ds-circuit-breaker-bulkhead/)) آسیب یک وابستگی کند را محدود می‌کند.

شاید تکنیک {{< term "five-whys" "پنج چرا" >}} را بشناسید: پنج بار «چرا؟» بپرسید. این تکنیک یک زنجیره را دنبال می‌کند و معمولاً همان‌جا می‌ایستد که کسی که جواب می‌دهد می‌ایستد، اغلب روی یک آدم («چرا؟ یکی فراموش کرد چک کند»). من یک نمودار علّی کوچک را ترجیح می‌دهم که بتواند شاخه داشته باشد. از چپ به راست بخوانیدش، «به‌خاطر»:

```text
503s <- pool wait timeouts <- capacity (2 x 2.5/s) < traffic (10/s)
   |-- pool_max=2 accepted      <- no validation, no canary
   |-- dependency 4x slower     <- no latency alert
   '-- noticed after users hurt <- alert on errors only
```

خط بالا سازوکار است: درخواست‌ها شکست می‌خورند چون برای گرفتن اتصال زیادی منتظر می‌مانند، چون pool (دو slot که هرکدام با ۴۰۰ میلی‌ثانیه ۲٫۵ درخواست در ثانیه را جواب می‌دهد) از ترافیک (۱۰ در ثانیه) کوچک‌تر است. سه شاخه دلیل‌هایی‌اند که سیستم این را اجازه داد. هر شاخه به چیزی ختم می‌شود که تیم می‌تواند عوضش کند.

## زبان بدون سرزنش

blameless یعنی کسی مسئول نیست؟ نه. یعنی می‌پرسیم سیستم چه چیزی را ممکن کرده بود، نه اینکه چه کسی را تنبیه کنیم. چند بازنویسی تفاوت را نشان می‌دهد:

- «Bob یک config بد push کرد» می‌شود «تغییر config نه validation داشت و نه rollout مرحله‌ای».
- «on-call دیر واکنش نشان داد» می‌شود «runbook نگفته بود اولین حرکت rollback است».
- «خطای انسانی» می‌شود هیچ. اگر یک نفر می‌توانست این کار را بکند، سیستم آن را ممکن کرده بود و جمله‌ی درست همین است.

## یک postmortem چه شکلی است

این نسخه‌ی خوبِ سند دمو است، `postmortem.md`. بخش‌های استاندارد را دارد و هر بخش به یک پرسش جواب می‌دهد:

```markdown
# Postmortem: 503 spike after a pool-size config change (STAGED INCIDENT)

## Summary
A config rollout lowered the DB pool limit from 10 to 2. Five seconds later the dependency slowed from 100 ms to 400 ms. Capacity fell below traffic and requests timed out waiting for a connection.

## Impact
201 of 900 requests failed (22.3%) over about 38 seconds. 0.16% of the assumed 30-day error budget.

## Timeline
See the table produced by cmd/timeline (t+0:00 = first failed request).

## Contributing factors
- The config change had no validation of a minimum pool size.
- The rollout went to 100% at once, with no canary.
- The dependency latency rose with no alert of its own.
- The alert watched only the error rate, so it fired after users were hurt.

## What went well
- The alert fired 7.7 s after the first error.
- The rollback was one config change, not a deploy.

## What went badly
- The new config reached all instances at once.
- Nobody could see pool saturation on a dashboard.

## Where we got lucky
- The dependency slowdown came after the change; had it come first the cause would have been unclear.

## Action items
| ID | Action | Owner | Due | Priority |
|----|--------|-------|-----|----------|
| AI-1 | Reject pool_max below 4 in config validation | backend team | 2027-06-01 | P1 |
| AI-2 | Roll config out to 10% of instances first | release engineer | 2027-06-15 | P1 |
| AI-3 | Alert on pool wait time p95 | SRE on-call | 2027-06-08 | P2 |
```

(در فایلی که lint کردم، Summary نوشته بود «Seven seconds later» یعنی «هفت ثانیه بعد». این غلط است: کندی وابستگی پنج ثانیه بعد از تغییر شروع می‌شود، همان‌طور که timeline نشان می‌دهد. بالا اصلاحش کردم. نتیجه‌ی lint به آن جمله بستگی ندارد.)

چطور بخوانیمش: Summary در سه جمله می‌گوید چه شد. Impact اندازه‌ی آسیب را با عدد می‌گوید. Contributing factors همان فهرست بخش قبل است. «What went well» به اندازه‌ی شکست‌ها مهم است: به تیم می‌گوید چه چیزی را نگه دارد. «Where we got lucky» بخشی است که آدم‌ها از آن می‌گذرند و مهم است، چون شانس ریسکی است که هنوز اتفاق نیفتاده. Action itemها هدف کل سند هستند. هرکدام یک **نقش** مالک (نه نام آدم)، یک تاریخ و یک اولویت دارد.

## سند را lint کنیم

سندی مثل این می‌تواند بی‌آنکه کسی بفهمد دوباره به سمت سرزنش برگردد. برای همین دمو یک بررسی‌کننده‌ی کوچک دارد، `pmlint`. چک می‌کند هر هشت بخش هست، هر action item یک نقش مالک، یک تاریخ به شکل `YYYY-MM-DD` و یک اولویت P0 یا P1 یا P2 دارد، و نام کوچک و عبارت‌هایی مثل «human error» را علامت می‌زند. این هم اجرا روی پیش‌نویس خوب و روی یک پیش‌نویس عمداً سرزنش‌آمیز (اجرای دوم با خطا تمام می‌شود، که همان هدف است):

```text
postmortem.md
  ok (3 action items)
blamey.md
  FAIL missing section "Where we got lucky"
  FAIL line 4: first name "Bob" (use a role)
  FAIL line 13: blamey phrase "human error"
  FAIL line 13: blamey phrase "careless"
  FAIL line 13: blamey phrase "should have known"
  FAIL line 13: first name "Bob" (use a role)
  FAIL line 29: first name "Bob" (use a role)
  FAIL line 29: owner "Bob" is not a role
  FAIL line 30: due date "soon" is not YYYY-MM-DD
```

پیش‌نویس خوب با سه action item رد می‌شود. پیش‌نویس سرزنش‌آمیز نه مورد را رد می‌کند: یک بخش گم‌شده، اسم «Bob» در خلاصه و در عامل‌ها و در جدول action، سه عبارت سرزنش‌آمیز در یک خط، و یک action item با تاریخ «soon». regex فقط نام‌هایی را می‌گیرد که در فهرستش گذاشته‌ام، پس این یک تلنگر است، نه داور.

## روالی که خودم ترجیح می‌دهم (نظر من)

ظرف چند روز بنویسید، تا وقتی که آدم‌ها هنوز یادشان هست. در جلسه‌ای مرور کنید که سؤالش «چه چیزی جلوی این را می‌گرفت؟» است و جایی منتشر کنید که همه‌ی تیم‌ها بخوانند. action itemها را مثل هر کار دیگری دنبال کنید، وگرنه postmortem نمایش است: action itemهای انجام‌نشده {{< term "technical-debt" "بدهی فنی" >}} با تاریخ‌اند ([بدهی فنی](/fa/posts/eng-technical-debt/)).

## عادت‌هایی که postmortem را بی‌سرزنش نگه می‌دارد

- **timeline را از لاگ بسازید نه حافظه.** همه‌ی ساعت‌ها را در یک timezone نگه دارید، وگرنه سر ترتیب رویدادها بحث می‌شود.
- **آنچه خوب پیش رفت و جاهایی که شانس آوردید را بنویسید.** شانس یک ریسک است و تا وقتی تمام نشده دیده نمی‌شود.
- **برای هر action item نقش مالک، تاریخ و اولویت بگذارید.** بدون این‌ها بی‌صدا می‌پوسد.
- **نام آدم‌ها را منتشر نکنید و «بیشتر دقت کنیم» را action item ننویسید.** اولی آدم را سرزنش می‌کند و دومی را نه می‌شود چک کرد و نه تمام.

## تمرین

یک هشدار «تأخیر وابستگی بالای ۲۵۰ میلی‌ثانیه» به مدل اضافه کنید و TTD را دوباره حساب کنید. آیا قبل از اولین خطا فعال می‌شود؟

## قدم بعدی

مقاله‌ی بعد «کار با کد legacy» است. action itemها فقط وقتی کمک می‌کنند که کدی که به آن می‌خورند را بشود امن تغییر داد، و کد قدیمی اغلب دقیقاً این اجازه را نمی‌دهد.
