+++
date = '2027-04-19T10:00:00+03:30'
draft = false
title = 'ADR و مستندسازی تصمیم‌ها'
description = 'ADR و مستندسازی تصمیم‌ها: چهار سند در یک repo با Go، چکر روی مجموعه‌ی سالم و خراب، جایگزینی به‌جای ویرایش و ساخت خودکار فهرست.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["adr", "documentation", "architecture", "software-engineering", "go"]
cover = { image = "/images/covers/eng-adr-documentation.fa.png", alt = "ADR و مستندسازی تصمیم‌ها", hiddenInSingle = true }
+++

پست قبل، [بدهی فنی](/fa/posts/eng-technical-debt/)، با فهرستی از چیزهایی تمام شد که تصمیم گرفتیم رهایشان کنیم. فهرست می‌گوید چه تصمیمی گرفتیم، نه چرا. شش ماه بعد کسی می‌پرسد «چرا outbox را poll می‌کنیم؟» و جواب در یک گفت‌وگوی چت است که هیچ‌کس پیدایش نمی‌کند. {{< term "adr" "ADR" >}} (سند تصمیم معماری) فایل کوتاهی در repo است که «چرا» را نگه می‌دارد. مثل کد review می‌شود ([review مؤثر کد](/fa/posts/eng-code-review/)) و پست‌هایی مثل [طراحی API: نسخه‌بندی و صفحه‌بندی](/fa/posts/eng-api-design-versioning-pagination/) پر از تصمیم‌هایی‌اند که ثبت‌کردنی‌اند. نظرها با **به نظر من** مشخص شده‌اند و چکرها و خروجی git اجرا شده‌اند.

> Go 1.26. سرویس سفارش و چهار ADR آن ساختگی‌اند و با نویسنده‌ی جعلی و تاریخ ثابت در یک repo محلی ساخته شده‌اند. این تصمیم‌ها توصیه نیستند.

## قالب

از قالب Nygard استفاده می‌کنم (عنوان، Status، Context، Decision، Consequences). این ADR شماره‌ی ۴ است که جای ADR شماره‌ی ۲ را می‌گیرد:

```markdown
# 4. Run several relays with SKIP LOCKED

## Status

Accepted

Supersedes [2. Use an outbox in Postgres](0002-use-an-outbox-in-postgres.md)

## Context

ADR 2 chose one polling relay. It stopped publishing during a deploy and events were late. We still want the outbox itself.
```

مجموعه: ۱ ثبت تصمیم‌ها، ۲ استفاده از {{< term "outbox-pattern" "outbox" >}} به‌جای dual write، ۳ استفاده از {{< term "jetstream" "JetStream" >}} برای رویدادها، ۴ اجرای چند relay. consumerها {{< term "idempotency" "idempotent" >}} می‌مانند، مثل [پست outbox](/fa/posts/go-outbox-pattern-nats/). جایگزین رایج MADR است که در `docs/adr-madr/` کنارش گذاشتم:

```markdown
# Use NATS JetStream for events
* Status: accepted
## Considered Options
* NATS JetStream
* Kafka
## Decision Outcome
Chosen option: "NATS JetStream", because the team already runs NATS.
```

**به نظر من** تفاوت کوچک است: MADR شما را مجبور می‌کند گزینه‌ها را فهرست کنید و Nygard کوتاه‌تر است. یکی را انتخاب کنید.

## Context و Consequences خوب

- Context نیروها را می‌گوید، نه راه‌حل را: چه چیزی آزار می‌داد، چه محدودیتی هست، چه چیزی را نمی‌دانیم.
- Consequences باید هزینه داشته باشد. ADR که همه‌ی پیامدهایش خوب است شبیه تبلیغ می‌شود. ADR 2 «single point of failure» را می‌پذیرد؛ ADR 4 بعداً دقیقاً همان را رفع کرد.
- آن را در pull requestی بنویسید که تصمیم را پیاده می‌کند.

## وضعیت‌ها و تغییرناپذیری

وضعیت‌هایی که استفاده می‌کنم: proposed، accepted، superseded، deprecated. **به تجربه‌ی من** قاعده‌ای که ADRها را قابل‌اعتماد نگه می‌دارد این است: ADR پذیرفته‌شده را هرگز بازنویسی نکنید. غلط تایپی و خط status مجازند، بقیه نه. تغییر نظر یک ADR تازه است که می‌گوید «Supersedes 2» و ADR 2 می‌شود «Superseded by 4». تاریخچه صادق می‌ماند.

## یک چکر

قاعده‌ها بدون ماشین می‌پوسند، پس یک برنامه‌ی کوچک Go نوشتم (فقط کتابخانه‌ی استاندارد، حدود ۲۰۰ خط). این‌ها را بررسی می‌کند: شماره‌گذاری پیوسته، تطابق slug نام فایل با عنوان، بخش‌های لازم، وضعیت‌های مجاز و اینکه هر لینک `Supersedes` به فایلی برود که «Superseded by» همین ADR است. روی مجموعه‌ی سالم:

```text
$ go run ./cmd/adrcheck check docs/adr
ok
```

روی نسخه‌ای که عمداً خرابش کردم (نام فایل عوض‌شده، وضعیت ساختگی «Approved»، نبودن ADR 3، بخش حذف‌شده و ADR 2 که دیگر superseded نیست):

```text
$ go run ./cmd/adrcheck check testdata/broken
FAIL 0001-record-decisions.md: filename slug should be "record-architecture-decisions"
FAIL 0002-use-an-outbox-in-postgres.md: status "approved" is not one of proposed/accepted/superseded/deprecated
FAIL 0004-run-several-relays-with-skip-locked.md: expected number 0003 (numbering must be sequential)
FAIL 0005-use-nats-jetstream-for-events.md: missing or empty section Consequences
FAIL 0004-run-several-relays-with-skip-locked.md: supersedes 0002-use-an-outbox-in-postgres.md, but that file is not marked 'Superseded by' this one
5 problem(s)
```

همین برنامه حالت `links` هم برای لینک‌های نسبی markdown دارد:

```text
$ go run ./cmd/adrcheck links testdata/badlinks
FAIL testdata/badlinks/README.md: broken link runbook.md
FAIL testdata/badlinks/README.md: broken link adr/0009-nope.md
2 problem(s)
```

جایش در {{< term "ci" "CI" >}} است. این workflow را نوشتم ولی روی GitHub اجرا نکردم، فقط دو دستور را محلی اجرا کردم:

```yaml
name: docs
on:
  pull_request:
    paths: ["docs/**", "cmd/adrcheck/**"]
jobs:
  adr:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
      - run: go run ./cmd/adrcheck check docs/adr
      - run: go run ./cmd/adrcheck links docs
```

ابزار فایل `docs/adr/README.md` را هم از روی فایل‌ها می‌سازد (`adrcheck index docs/adr`)، پس هیچ‌کس فهرست را دستی ویرایش نمی‌کند:

```text
| # | Title | Status |
|---|---|---|
| 1 | Record architecture decisions | accepted |
| 2 | Use an outbox in Postgres | superseded |
| 3 | Use NATS JetStream for events | accepted |
| 4 | Run several relays with SKIP LOCKED | accepted |
```

## چرا داخل repo

تاریخچه حتی بعد از تغییر نام دنبال فایل می‌آید:

```text
$ git log --follow --format="%h %ad %s" --date=short -- docs/adr/0002-use-an-outbox-in-postgres.md
5e19d0e 2027-03-15 ADR 4: run several relays; mark ADR 2 superseded
0f3b713 2027-02-22 ADR 2: clearer title, rename file
f45c20c 2027-02-08 Add polling outbox relay (ADR 0002)
```

و `git blame` روی کد به commitی می‌رسد که ADR را همراه relay اضافه کرده:

```text
$ git blame -L 6,6 internal/outbox/relay.go
f45c20ca (Roham 2027-02-08 6) // PollInterval is how often the single relay polls. See docs/adr/0002.
```

صفحه‌ی wiki نمی‌تواند در همان commit کدی باشد که توضیحش می‌دهد.

## کدام سند؟

| سند | به چه جواب می‌دهد | کجا | قاعده‌ی سرانگشتی من |
|---|---|---|---|
| {{< term "rfc" "RFC" >}} / design doc | چه بسازیم و با چه جایگزین‌هایی | پیش از کار | بلند، بحث‌شده، ممکن است دور ریخته شود |
| ADR | چه تصمیمی گرفتیم و چرا | کنار کد | کوتاه، تغییرناپذیر |
| README | این چیست و چطور اجرا شود | کنار کد | فقط وضع فعلی |
| {{< term "runbook" "Runbook" >}} | ساعت ۳ شب چه کنم | کنار سرویس | دائم ویرایش می‌شود |

این جدول نظر من است، نه استاندارد.

## چه وقت ننویسیم

برای انتخاب‌های به‌راحتی برگشت‌پذیر (نام متغیر، یک قاعده‌ی lint) و تصمیم‌هایی که از کد معلوم‌اند ننویسید. **به نظر من** محک این است: آیا هم‌تیمی تازه‌وارد یک سال بعد ممکن است از سر ناآگاهی آن را برگرداند؟

## چند نکته‌ی مهم

- ADRی که بعد از ماجرا نوشته شود بیشتر توجیه می‌کند تا توضیح بدهد.
- ADR قدیمی را «برای درست ماندن» ویرایش نکنید. جایگزینش کنید.
- وضعیت‌ها فقط وقتی معنی دارند که چکر با دروغشان شکست بخورد.
- چکر ساختار را ثابت می‌کند، نه خوب‌بودن استدلال را. review هنوز لازم است.

## تمرین

برای تصمیمی که تیم‌تان ماه گذشته گرفت یک ADR با همین قالب بنویسید، با یک پیامد منفی صادقانه. بعد نام فایل را عوض کنید و ببینید چکر چه می‌گوید.

## قدم بعدی

پست بعد «feature flag و trunk-based development» است.
