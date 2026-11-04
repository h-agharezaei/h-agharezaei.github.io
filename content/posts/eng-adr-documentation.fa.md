+++
date = '2027-04-19T10:00:00+03:30'
draft = false
title = 'ADR و مستندسازی تصمیم‌ها'
contentType = 'tutorial'
description = 'ADR و مستندسازی تصمیم‌ها: چهار سند در یک repo با Go، چکر روی مجموعه‌ی سالم و خراب، جایگزینی به‌جای ویرایش و ساخت خودکار فهرست.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["adr", "documentation", "architecture", "software-engineering", "go"]
cover = { image = "/images/covers/eng-adr-documentation.fa.png", alt = "ADR و مستندسازی تصمیم‌ها", hiddenInSingle = true }
+++

شش ماه بعد از یک تصمیم، هم‌تیمی تازه‌ای می‌پرسد: «چرا به‌جای انتشار مستقیم روی broker، outbox را poll می‌کنیم؟» کسی یادش نیست. یک نفر نیمه‌یادش هست که بحثی طولانی در چت شده بود، کسی پیدایش نمی‌کند، و تیم یا دوباره از صفر سر همان تصمیم بحث می‌کند یا بدتر، بدون اینکه بداند آن تصمیم از چه چیزی محافظت می‌کرد، آن را برمی‌دارد.

راه‌حل قدیمی و ارزان است: «چرا» را بنویسید، توی repo، کنار کد. {{< term "adr" "ADR" >}} (سند تصمیم معماری) یک فایل متنی کوتاه است که یک تصمیم، دلیل‌هایش و هزینه‌اش را نگه می‌دارد. دفتر بدهی در [بدهی فنی](/fa/posts/eng-technical-debt/) می‌گفت چه چیزی خراب است و چه باید کرد؛ ADR می‌گوید چرا سیستم به این شکل ساخته شده. مثل کد review می‌شود، همان‌طور که در [code review مؤثر](/fa/posts/eng-code-review/) آمد، و پستی مثل [طراحی API: نسخه‌بندی و pagination](/fa/posts/eng-api-design-versioning-pagination/) پر از تصمیم‌هایی است که ارزش ثبت‌شدن دارند. نظرهای خودم را با **به نظر من** مشخص کرده‌ام. بررسی‌ها و خروجی‌های git اجرا شده‌اند.

> demo یک repo کوچک Go برای یک سرویس سفارش با چهار ADR است. سرویس و ADRها ساختگی‌اند، با نویسنده‌ی جعلی و تاریخ ثابت، و این تصمیم‌ها توصیه نیستند. در اجرای اولیه با Go 1.26 اجرایش کردم و برای این ویرایش همه‌ی دستورهای زیر را با Go 1.27.3 دوباره اجرا کردم.

## قالب

ADR عمداً کوتاه است. من از قالبی استفاده می‌کنم که Michael Nygard هنگام معرفی این ایده پیشنهاد کرد: عنوان (Title)، وضعیت (Status)، زمینه (Context)، تصمیم (Decision) و پیامدها (Consequences). این ADR شماره‌ی ۴ در demo است، کامل، تا ببینید یک نمونه‌ی واقعی چه شکلی دارد. جای ADR شماره‌ی ۲ را می‌گیرد:

```markdown
# 4. Run several relays with SKIP LOCKED

## Status

Accepted

Supersedes [2. Use an outbox in Postgres](0002-use-an-outbox-in-postgres.md)

## Context

ADR 2 chose one polling relay. It stopped publishing during a deploy and events were late. We still want the outbox itself.

## Decision

We keep the outbox table from ADR 2, but run two or more relays. Each claims rows with `SELECT ... FOR UPDATE SKIP LOCKED` inside a transaction.

## Consequences

A relay can restart without stopping delivery. Order between events of different orders is no longer guaranteed, and a crash after publish but before commit still duplicates an event, so consumers stay idempotent.
```

بخش به بخش این‌طور خوانده می‌شود.

- **Title.** یک شماره و یک جمله‌ی کوتاه امری: «Run several relays with SKIP LOCKED». شماره هرگز عوض نمی‌شود؛ رکوردهای دیگر با آن به این یکی اشاره می‌کنند.
- **Status.** تصمیم الان در چه وضعیتی است: proposed، accepted، superseded یا deprecated. این یکی accepted است و می‌گوید ADR شماره‌ی ۲ را supersede می‌کند، یعنی جایش را می‌گیرد.
- **Context.** موقعیتی که مجبور به تصمیم کرد: چه چیزی آزار می‌داد و چه محدودیت‌هایی بود. هنوز اسمی از راه‌حل نمی‌آید. این‌جا: یک relay هنگام deploy از کار افتاد و رویدادها دیر رسیدند.
- **Decision.** چه چیزی را انتخاب کردیم، در یکی دو جمله و با جمله‌ی معلوم: «جدول outbox را نگه می‌داریم، اما دو relay یا بیشتر اجرا می‌کنیم.»
- **Consequences.** از این تصمیم چه چیزی نتیجه می‌شود، خوب و بد. این‌جا بخش بد صریح آمده: ترتیب بین سفارش‌ها از دست می‌رود و تکرار رویداد هنوز ممکن است.

سه رکورد دیگر هم همین شکل را دارند. ADR شماره‌ی ۱ می‌گوید اصلاً ADR نگه می‌داریم. ADR شماره‌ی ۲ به‌جای نوشتن جداگانه در پایگاه داده و broker («dual write») از یک جدول {{< term "outbox-pattern" "outbox" >}} استفاده می‌کند. ADR شماره‌ی ۳ برای رویدادها {{< term "jetstream" "JetStream" >}} را انتخاب می‌کند. ADR شماره‌ی ۴ همین است که بالا آمد. consumerها باید {{< term "idempotency" "idempotent" >}} بمانند، یعنی پردازش یک رویداد برای بار دوم ضرری نزند، همان‌طور که در [پست outbox](/fa/posts/go-outbox-pattern-nats/) دیدیم.

یک قالب جایگزین رایج MADR است، یک قالب Markdown با فهرست صریح گزینه‌ها. ADR شماره‌ی ۳ را به آن سبک هم نوشتم و کنار نمونه‌ی دیگر در `docs/adr-madr/` گذاشتم:

```markdown
# Use NATS JetStream for events
* Status: accepted
## Considered Options
* NATS JetStream
* Kafka
## Decision Outcome
Chosen option: "NATS JetStream", because the team already runs NATS.
```

این گزیده‌ی کوتاه‌شده‌ی فایل است. **به نظر من** تفاوت کم است: MADR مجبورتان می‌کند گزینه‌های ردشده را بنویسید و قالب Nygard کوتاه‌تر است. یکی را انتخاب کنید و به همان بچسبید.

## Context و Consequences خوب

نوشتن Title و Status و Decision آسان است. بیشتر ارزش، و بیشتر اشتباه‌ها، در دو بخش دیگر است.

- Context نیروها را می‌گوید، نه راه‌حل را: چه چیزی آزار می‌داد، چه محدودیت‌هایی هست و چه چیزی را هنوز نمی‌دانیم. اگر context از قبل برای جواب استدلال کند، خواننده نمی‌تواند تصمیم را بسنجد.
- Consequences حتماً باید یک هزینه داشته باشد. ADRی که پیامدهایش همه خوب است مثل متن فروش می‌خواند. ADR شماره‌ی ۲ اعتراف می‌کند «single point of failure» است و ADR شماره‌ی ۴ بعدها دقیقاً همین را درست کرد. این پیوند بین دو رکورد فقط چون اولی صادق بود ممکن شد.
- ADR را در همان pull requestی بنویسید که تصمیم را پیاده می‌کند، تا وقتی که دلیل‌ها هنوز تازه‌اند.

## وضعیت‌ها و تغییرناپذیری

وضعیت‌هایی که من به کار می‌برم proposed، accepted، superseded و deprecated است. **به تجربه‌ی من** یک قاعده ADRها را قابل اعتماد نگه می‌دارد: ADR پذیرفته‌شده را هرگز بازنویسی نکنید. می‌توانید غلط تایپی را درست کنید و خط وضعیت را عوض کنید، همین. اگر نظرتان عوض شد، ADR تازه‌ای می‌نویسید که می‌گوید «Supersedes 2» و ADR شماره‌ی ۲ خط «Superseded by 4» را می‌گیرد. چیزی حذف نمی‌شود، پس خواننده هم می‌بیند تیم آن موقع چه فکر می‌کرد و هم الان چه فکر می‌کند.

## یک checker

قاعده‌هایی مثل این اگر ماشینی اجرایشان نکند می‌پوسند. برای همین یک برنامه‌ی کوچک Go به نام `adrcheck` نوشتم که فقط از کتابخانه‌ی استاندارد استفاده می‌کند (۱۹۹ خط). بررسی می‌کند شماره‌گذاری پشت‌سرهم باشد، نام فایل با عنوان بخواند، بخش‌های لازم موجود باشند، وضعیت یکی از وضعیت‌های مجاز باشد، و هر لینک `Supersedes` به فایلی اشاره کند که خودش «superseded توسط همین» علامت خورده است. روی مجموعه‌ی سالم این را چاپ می‌کند:

```text
$ go run ./cmd/adrcheck check docs/adr
ok
```

checker فقط وقتی باورپذیر است که دیده باشم شکست می‌خورد. پس از مجموعه یک نسخه ساختم و عمداً خرابش کردم: یک فایل با نام عوض‌شده، یک وضعیت ساختگی «Approved»، ADR شماره‌ی ۳ که نیست، یک بخش حذف‌شده، و ADR شماره‌ی ۲ که دیگر superseded علامت نخورده:

```text
$ go run ./cmd/adrcheck check testdata/broken
FAIL 0001-record-decisions.md: filename slug should be "record-architecture-decisions"
FAIL 0002-use-an-outbox-in-postgres.md: status "approved" is not one of proposed/accepted/superseded/deprecated
FAIL 0004-run-several-relays-with-skip-locked.md: expected number 0003 (numbering must be sequential)
FAIL 0005-use-nats-jetstream-for-events.md: missing or empty section Consequences
FAIL 0004-run-several-relays-with-skip-locked.md: supersedes 0002-use-an-outbox-in-postgres.md, but that file is not marked 'Superseded by' this one
5 problem(s)
```

هر خط یک فایل و قاعده‌ای را که شکسته نام می‌برد و پنج خط با پنج چیزی که خراب کردم یکی است. خط آخر جالب‌ترین است: حالتی که ADR شماره‌ی ۴ ادعا می‌کند جای ADR شماره‌ی ۲ را گرفته، اما ADR شماره‌ی ۲ این را نمی‌گوید. (برنامه با کد خروج ۱ هم تمام می‌شود، پس CI قرمز می‌شود.)

همین برنامه یک حالت `links` هم دارد که لینک‌های نسبی markdown بین مستندات را می‌سنجد:

```text
$ go run ./cmd/adrcheck links testdata/badlinks
FAIL testdata/badlinks/README.md: broken link runbook.md
FAIL testdata/badlinks/README.md: broken link adr/0009-nope.md
2 problem(s)
```

هر دو دستور جایشان در {{< term "ci" "CI" >}} است. workflow زیر را نوشتم، اما روی GitHub اجرایش نکردم. فقط همان دو دستور را به‌صورت محلی اجرا کردم:

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

این workflow فقط وقتی اجرا می‌شود که یک pull request به مستندات یا خود checker دست بزند، و دو دستور را به ترتیب اجرا می‌کند.

ابزار می‌تواند فهرست `docs/adr/README.md` را هم از روی خود فایل‌ها بسازد (`adrcheck index docs/adr`)، پس کسی فهرست را دستی ویرایش نمی‌کند و قدیمی هم نمی‌شود:

```text
| # | Title | Status |
|---|---|---|
| 1 | [Record architecture decisions](0001-record-architecture-decisions.md) | accepted |
| 2 | [Use an outbox in Postgres](0002-use-an-outbox-in-postgres.md) | superseded |
| 3 | [Use NATS JetStream for events](0003-use-nats-jetstream-for-events.md) | accepted |
| 4 | [Run several relays with SKIP LOCKED](0004-run-several-relays-with-skip-locked.md) | accepted |
```

(این بخش جدول فایل تولیدشده است؛ بالایش یک عنوان و یک خط «این فایل را ویرایش نکنید» هم هست.)

## چرا در repo

تصمیمی که در wiki یا چت است از کدی که توضیحش می‌دهد جداست. در repo، git آن‌ها را کنار هم نگه می‌دارد. تاریخچه حتی از تغییر نام جان به در می‌برد. این تاریخچه‌ی ADR شماره‌ی ۲ است که یک بار نامش عوض شده:

```text
$ git log --follow --format="%h %ad %s" --date=short -- docs/adr/0002-use-an-outbox-in-postgres.md
5e19d0e 2027-03-15 ADR 4: run several relays; mark ADR 2 superseded
0f3b713 2027-02-22 ADR 2: clearer title, rename file
f45c20c 2027-02-08 Add polling outbox relay (ADR 0002)
```

`--follow` باعث می‌شود git تاریخچه را از روی تغییر نام هم ادامه دهد. قدیمی‌ترین خط نشان می‌دهد ADR در همان commit کد relay اضافه شد. نکته‌ی مفید همین است. یک کامنت در کد به رکورد اشاره می‌کند و `git blame` از کد به همان commit می‌رسد:

```text
$ git blame -L 6,6 internal/outbox/relay.go
f45c20ca (Roham 2027-02-08 10:00:00 +0330 6) // PollInterval is how often the single relay polls. See docs/adr/0002.
```

یک صفحه‌ی wiki نمی‌تواند در همان commit کدی باشد که توضیحش می‌دهد.

## کدام سند؟

ADR تنها نوع سند نیست و جای بقیه را نمی‌گیرد. این جدول نشان می‌دهد من آن‌ها را چطور از هم جدا می‌کنم:

| سند | به چه جواب می‌دهد | کجا زندگی می‌کند | قاعده‌ی سرانگشتی من |
|---|---|---|---|
| {{< term "rfc" "RFC" >}} / design doc | چه چیزی بسازیم، با جایگزین‌ها | پیش از کار | بلند، بحث‌شده، ممکن است دور ریخته شود |
| ADR | چه تصمیمی گرفتیم و چرا | کنار کد | کوتاه، تغییرناپذیر |
| README | این چیست و چطور اجرایش کنم | کنار کد | فقط وضعیت فعلی |
| {{< term "runbook" "Runbook" >}} | ساعت ۳ بامداد چه کنم | کنار سرویس | دائماً ویرایش می‌شود |

این جدول نظر من است، نه یک استاندارد.

## کِی ننویسیم

برای انتخاب‌هایی که برگشتشان آسان است (اسم یک متغیر، یک قاعده‌ی lint) یا تصمیم‌هایی که از خود کد پیداست ADR ننویسید. **به نظر من** محک این است: آیا یک هم‌تیمی تازه، یک سال بعد، محتمل است که این را از سر ناآگاهی برگرداند؟ اگر بله، بنویسید.

## ADRها چطور ارزششان را از دست می‌دهند

- **نوشتن بعد از ماجرا.** ADRی که مدت‌ها بعد از تصمیم نوشته شود بیشتر توجیه می‌کند تا توضیح بدهد.
- **ویرایش برای «درست ماندن».** ADR قدیمی را ویرایش نکنید. supersede کنید تا تاریخچه صادق بماند.
- **وضعیت‌هایی که دروغ می‌گویند.** وضعیت فقط وقتی معنا دارد که checker در صورت دروغ بودنش شکست بخورد.
- **ساختار یعنی کیفیت نیست.** checker ساختار را ثابت می‌کند، نه اینکه استدلال خوب است. خواندن را همچنان reviewerها باید انجام دهند.

## تمرین

برای تصمیمی که تیمتان ماه پیش گرفته یک ADR با قالب بالا بنویسید، با یک پیامد منفی صادقانه. بعد نام فایل را عوض کنید و ببینید checker چه می‌گوید.

## قدم بعدی

پست بعدی «feature flag و trunk-based development» است. ADR تصمیم را بعد از گرفتن ثبت می‌کند. سؤال بعدی این است که چطور یک تغییر را حتی بعد از انتشار برگشت‌پذیر نگه داریم.
