+++
date = '2027-05-16T10:00:00+03:30'
draft = false
title = 'postmortem بدون سرزنش'
description = 'postmortem بدون سرزنش با یک حادثه‌ی ساختگی در Go: timeline از لاگ، TTD/TTM/TTR، عامل‌های مؤثر، action item و lint قابل اجرای سند.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["postmortem", "incident", "blameless", "software-engineering", "go", "slog"]
cover = { image = "/images/covers/eng-postmortems-blameless.fa.png", alt = "postmortem بدون سرزنش", hiddenInSingle = true }
+++

پست قبل، [SLI، SLO و error budget](/fa/posts/eng-sli-slo-error-budgets/)، گفت یک {{< term "slo" "SLO" >}} چقدر شکست را می‌پذیرد. این پست درباره‌ی کاری است که بعد از مصرف شدن بخشی از آن {{< term "error-budget" "error budget" >}} در یک حادثه باید کرد. **این حادثه روی ماشین خودم ساختگی (staged) است**: نه کاربر واقعی هست، نه آدم واقعی؛ نام‌ها و نقش‌ها ساختگی‌اند. لاگ‌ها، عددها و خروجی lint اجرای واقعی یک دموی کوچک Go هستند. قضاوت‌ها را «نظر من» نوشته‌ام.

{{< term "postmortem" "postmortem" >}} بررسی نوشته‌شده‌ای است که از روی شواهد ساخته می‌شود. مرتبط: [پیکربندی، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/)، [connection pooling و شکست‌هایش](/fa/posts/db-connection-pooling/)، [طراحی pipeline برای CI/CD](/fa/posts/eng-ci-cd-pipeline-design/).

> Go 1.26، `go test -race` سبز بود. «سرویس» یک مدل با زمان مجازی است (مولد seed‌دار، ساعت تزریق‌شده، بدون socket و بدون sleep)، پس timestampها در هر اجرا یکی‌اند.

## حادثه‌ی ساختگی

ساعت 09:00:15 یک تغییر config سقف pool را از 10 به 2 می‌برد. پنج ثانیه بعد وابستگی از 100 به 400 میلی‌ثانیه کند می‌شود. دو slot با 400 میلی‌ثانیه حدود 5 درخواست در ثانیه را جواب می‌دهند و ترافیک حدود 10 است. درخواست‌ها منتظر connection می‌مانند و بعد از 1 ثانیه تسلیم می‌شوند. سرویس {{< term "structured-logging" "لاگ ساختاریافته" >}} با `slog` به شکل JSON و یک فایل شمارنده می‌نویسد:

```text
{"level":"ERROR","msg":"request","ts":"...","id":...,"status":503,"wait_ms":1000,"err":"pool wait timeout","pool_max":2}
requests_total{status="200"} 699
requests_total{status="503"} 201
```

قاعده‌ی alert این است: «نرخ خطا حداقل 20٪ در 10 ثانیه، هر 5 ثانیه بررسی». mitigation (rollback) 30 ثانیه بعد از alert انجام می‌شود؛ این تأخیر فرض من است، نه اندازه‌گیری از کسی.

## timeline از روی شواهد

برنامه‌ی دوم فقط `service.jsonl` را می‌خواند. `t+0:00` اولین درخواست ناموفق است:

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
requests=900 failed=201 (22.3%)
assumed SLO 99.5% at 10 rps for 30 days: budget = 129600 failed requests; burned 0.16%
```

TTD زمان تشخیص، TTM زمان مهار و TTR زمان بازیابی است، هر سه از شروع اثر. سه سؤال را جدا می‌کنند: فهمیدیم؟ خونریزی را بستیم؟ واقعاً تمام شد؟ عدد 0.16٪ فرضِ 10 درخواست در ثانیه در 30 روز را دارد که ساختگی است؛ محاسبه‌ی واقعی budget ترافیک واقعی شما را لازم دارد.

## عامل‌های مؤثر، نه «علت اصلی»

**نظر من:** «علت اصلی» به صورت مفرد بقیه را پنهان می‌کند. اینجا کندی وابستگی به تنهایی pool با اندازه‌ی 10 را خراب نمی‌کند (تست `TestHealthyConfigHasNoErrors` صفر خطا می‌بیند) و اندازه‌ی بد pool هم به تنهایی خراب نمی‌کند (تست دوم با وابستگی سریع هم صفر خطا دارد: 2 slot با 100 میلی‌ثانیه حدود 20 درخواست در ثانیه است). چهار چیز با هم جور شدند: نبود validation روی اندازه‌ی pool، rollout یک‌جا روی همه، نبود alert روی تأخیر وابستگی و alert‌ای که فقط خطا را می‌بیند. {{< term "circuit-breaker" "circuit breaker" >}} ([circuit breaker و bulkhead](/fa/posts/ds-circuit-breaker-bulkhead/)) آسیبِ وابستگی کند را محدود می‌کند. هر کدام یک {{< term "contributing-factor" "عامل مؤثر" >}} با اصلاح خودش است.

{{< term "five-whys" "پنج چرا" >}} یک زنجیره را می‌رود و همان‌جا می‌ایستد که پاسخ‌دهنده بایستد، اغلب روی یک آدم («چرا؟ یکی فراموش کرد چک کند»). من نمودار علّی کوچکی را ترجیح می‌دهم که شاخه داشته باشد:

```text
503s <- pool wait timeouts <- capacity (2 x 2.5/s) < traffic (10/s)
   |-- pool_max=2 accepted      <- no validation, no canary
   |-- dependency 4x slower     <- no latency alert
   '-- noticed after users hurt <- alert on errors only
```

## زبان بدون سرزنش

blameless یعنی کسی مسئول نیست؟ نه؛ یعنی می‌پرسیم سیستم چه چیزی را ممکن کرده بود. بازنویسی‌ها:

- «Bob یک config بد push کرد» می‌شود «تغییر config نه validation داشت و نه rollout مرحله‌ای».
- «on-call دیر واکنش نشان داد» می‌شود «runbook نگفته بود اولین حرکت rollback است».
- «خطای انسانی» می‌شود هیچ؛ اگر آدمی می‌توانست این کار را بکند، سیستم آن را ممکن کرده بود.

## سند را lint کنیم

`postmortem.md` بخش‌های استاندارد را دارد: Summary، Impact، Timeline، Contributing factors، What went well، What went badly، Where we got lucky و Action items. action itemها ردیف‌هایی با **نقش** مالک، تاریخ و اولویت‌اند. `pmlint` این‌ها را چک می‌کند و نام کوچک و عبارت‌هایی مثل «human error» را علامت می‌زند. اجرا روی پیش‌نویس خوب و یک پیش‌نویس عمداً سرزنش‌آمیز:

```text
postmortem.md
  ok (3 action items)
blamey.md
  FAIL missing section "Where we got lucky"
  FAIL line 4: first name "Bob" (use a role)
  FAIL line 13: blamey phrase "human error"
  FAIL line 13: blamey phrase "should have known"
  FAIL line 29: owner "Bob" is not a role
  FAIL line 30: due date "soon" is not YYYY-MM-DD
```

(سه خط مشابه حذف شده است.) regex فقط نام‌هایی را می‌گیرد که فهرست کرده‌ام؛ یک تلنگر است، نه داور.

## روال کار (نظر من)

ظرف چند روز بنویسید. در جلسه‌ای مرور کنید که سؤالش «چه چیزی جلوی این را می‌گرفت» است و جایی منتشر کنید که همه‌ی تیم‌ها بخوانند. action itemها را مثل هر کار دیگری دنبال کنید وگرنه postmortem نمایش است؛ موارد انجام‌نشده {{< term "technical-debt" "بدهی فنی" >}} با تاریخ‌اند ([بدهی فنی](/fa/posts/eng-technical-debt/)).

## چند نکته‌ی مهم

- timeline را از لاگ بسازید نه حافظه؛ ساعت‌ها را در یک timezone نگه دارید.
- آنچه خوب پیش رفت و جاهایی که شانس آوردیم را بنویسید: شانس یک ریسک است.
- action item بدون نقش مالک، تاریخ و اولویت می‌پوسد.
- نام آدم‌ها را منتشر نکنید و «بیشتر دقت کنیم» را action item ننویسید.

## تمرین

یک alert «تأخیر وابستگی بالای 250 میلی‌ثانیه» به مدل اضافه کنید و TTD را دوباره حساب کنید. آیا قبل از اولین خطا شلیک می‌کند؟

## قدم بعدی

پست بعدی «کار با کد legacy» است.
