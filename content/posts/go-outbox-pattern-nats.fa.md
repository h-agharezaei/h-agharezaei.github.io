+++
date = '2027-01-31T10:00:00+03:30'
draft = false
title = 'Outbox Pattern با Postgres و NATS در Go'
description = 'مشکل dual write را در Go حل می‌کنیم: جدول outbox در همان transaction، یک relay با SKIP LOCKED که در JetStream منتشر می‌کند، و اجرای واقعی crash.'
contentType = 'engineering'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "outbox", "postgres", "nats", "jetstream", "transactions"]
cover = { image = "/images/covers/go-outbox-pattern-nats.fa.png", alt = "Outbox Pattern با Postgres و NATS در Go", hiddenInSingle = true }
+++

مشتری سفارشی ثبت می‌کند. سرویس شما آن را در Postgres ذخیره می‌کند و باید به بقیه‌ی سیستم هم خبر بدهد: انبار باید موجودی را رزرو کند و سرویس ایمیل باید تأییدیه بفرستد. پس سرویس یک رویداد `order.created` را به یک message broker منتشر می‌کند، که اینجا NATS است.

این دو قدم در دو سیستم جدا هستند. Postgres می‌تواند نوشتن‌های خودش را با تراکنش یا همه یا هیچ کند ([تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/))، اما هیچ تراکنشی هم Postgres و هم NATS را پوشش نمی‌دهد. پس اگر پروسه بین این دو قدم بمیرد چه می‌شود؟ اگر بعد از ذخیره بمیرد، سفارش وجود دارد و هیچ‌کس هرگز خبردار نمی‌شود. اگر اول منتشر کنید و ذخیره شکست بخورد، همه از سفارشی باخبر می‌شوند که وجود ندارد. این **مسئله‌ی dual-write** است: در دو جا می‌نویسید و راهی نیست که هر دو نوشتن با هم موفق یا ناموفق شوند.

جواب استاندارد **{{< term "outbox-pattern" "الگوی outbox" >}}** است. ایده ساده است. رویداد را از داخل درخواست منتشر نکنید. به‌جایش آن را به‌شکل یک ردیف در جدولی به نام `outbox` و در *همان* تراکنش دیتابیسِ سفارش بنویسید. حالا سفارش و رویدادش با هم commit می‌شوند یا اصلاً نمی‌شوند، چون یک تراکنش Postgres است. یک حلقه‌ی پس‌زمینه‌ی جدا، به نام **relay**، بعداً ردیف‌های منتشرنشده را می‌خواند و به broker می‌فرستد. سینی روی میز اداری را در نظر بگیرید: نامه را در همان حرکتی که پرونده را بایگانی می‌کنید توی سینی می‌گذارید و مأمور پست بعداً سینی را می‌برد. نامه بین میز شما و صندوق پست گم نمی‌شود، هرچند ممکن است مأمور گاهی یک نامه را دو بار تحویل بدهد. می‌بینیم که دقیقاً همین رخ می‌دهد و چه باید کرد.

بر پایه‌ی جدول orders از [Postgres با pgx و sqlc](/fa/posts/go-postgres-pgx-sqlc/) کار می‌کنم. relay یک حلقه‌ی پس‌زمینه از همان جنس [الگوهای concurrency در Go](/fa/posts/go-concurrency-patterns/) است. انتشار از تشخیص تکراری JetStream استفاده می‌کند که در [idempotency در JetStream](/fa/posts/nats-jetstream-idempotency/) توضیح دادم.

> همه‌چیز دوباره با Go 1.27 روی یک PostgreSQL 18.3 واقعی (embedded-postgres نسخه‌ی v1.34.0 و pgx نسخه‌ی v5.11.0) و یک nats-server توکار v2.15.1 با nats.go نسخه‌ی v1.54.0 اجرا شده و خروجی‌های زیر از همین اجرا هستند. هر قدم یک پروسه‌ی جداست، پس crash یک `os.Exit(1)` واقعی است. ادعایی درباره‌ی زمان نمی‌کنم. عددهای داخل کروشه در خروجی‌ها شناسه‌ی پروسه هستند و در هر اجرا فرق می‌کنند (شناسه‌های اجرای اصلی را نگه داشته‌ام). کد یک مثال محلی است و ریپوی منتشرشده ندارد.

## شکست، این‌بار واقعی

اول نسخه‌های خراب، تا مشکل را ببینیم و فقط باور نکنیم. نسخه‌ی اول در دیتابیس می‌نویسد و بعد منتشر می‌کند. پروسه بین این دو می‌میرد:

```go
pool.Exec(ctx, `INSERT INTO orders (id, customer, cents) VALUES ('o-a', 'ali', 1500)`)
os.Exit(1) // crash here
js.Publish("orders.created", []byte(`{"order_id":"o-a"}`))
```

بعد از آن، فرمان کوچکی به نام `report` آنچه را در Postgres و در stream هست چاپ می‌کند:

```
[2089] order o-a committed
[2091] orders=[o-a] outbox rows=0 unpublished=0 stream messages=0
```

سفارش ذخیره شده و stream هیچ پیامی ندارد. هیچ‌کس هرگز از سفارش `o-a` خبردار نمی‌شود.

حالا ترتیب را برعکس کنید: اول منتشر کنید، بعد بنویسید، با یک نوشتن شکست‌خورده در دیتابیس (دمو مبلغ منفی وارد می‌کند که قید `CHECK` آن را رد می‌کند):

```
[2093] event for o-b published
[2093] insert o-b: ERROR: new row for relation "orders" violates check constraint "orders_cents_check" (SQLSTATE 23514)
[2095] orders=[o-a] outbox rows=0 unpublished=0 stream messages=1
[2095]   stream seq 1: {"order_id":"o-b"}
```

حالا در stream رویدادی برای سفارشی هست که وجود ندارد. اضافه‌کردن retry هیچ‌کدام از دو حالت را درست نمی‌کند، چون crash وضعیت retry را هم با پروسه می‌برد.

## جدول outbox

به‌جای منتشرکردن، سرویس رویداد را به‌شکل یک ردیف می‌نویسد. جدول این است:

```sql
CREATE TABLE outbox (
    id           bigserial   PRIMARY KEY,
    aggregate    text        NOT NULL,
    aggregate_id text        NOT NULL,
    type         text        NOT NULL,
    payload      jsonb       NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);
CREATE INDEX outbox_unpublished_idx ON outbox (id) WHERE published_at IS NULL;
```

`aggregate` نوع چیزی است که رویداد درباره‌ی آن است (`order`)، `aggregate_id` می‌گوید کدام‌یک، `type` می‌گوید چه شد (`created`) و `payload` بدنه‌ی رویداد است. `published_at` تا وقتی relay ردیف را نفرستاده خالی می‌ماند و index جزئی روی همان ردیف‌های خالی باعث می‌شود «منتشرنشده‌ها را بده» حتی وقتی جدول بزرگ شود سریع بماند.

`withTx` helper کوچک خودم دور `pgx.BeginFunc` است (با nil commit، با خطا rollback). سرویس سفارش و رویدادش را داخل آن می‌نویسد:

```go
err := withTx(ctx, pool, func(tx pgx.Tx) error {
    if _, err := tx.Exec(ctx, `INSERT INTO orders (id, customer, cents) VALUES ($1, 'ali', $2)`, id, cents); err != nil {
        return err
    }
    _, err := tx.Exec(ctx, `INSERT INTO outbox (aggregate, aggregate_id, type, payload)
        VALUES ('order', $1, 'created', $2)`, id, payload)
    return err
})
```

برای آزمودنش پروسه را درست پیش از commit crash دادم و بعد همین قدم را عادی دوباره اجرا کردم. خروجی این دو قدم، هرکدام با یک گزارش:

```
[2097] CRASH before commit
[2099] orders=[o-a] outbox rows=0 unpublished=0 stream messages=1
[2103] orders=[o-a,o-c2] outbox rows=1 unpublished=1 stream messages=1
```

گزارش اول (بعد از crash) نه سفارش `o-c1` را نشان می‌دهد و نه ردیف outbox: هر دو insert با هم rollback شدند. گزارش دوم (بعد از اجرای عادی) سفارش `o-c2` و دقیقاً یک ردیف outbox را نشان می‌دهد که منتظر انتشار است. (stream هنوز فقط همان رویداد یتیم `o-b` از آزمایش قبل را دارد.) سفارش و رویدادش دیگر نمی‌توانند جدا از هم وجود داشته باشند.

## relay

relay نیمه‌ی دوم است. در یک پروسه‌ی جدا اجرا می‌شود و در یک حلقه همین کار را می‌کند: یک دسته ردیف منتشرنشده را بخوان، هرکدام را به JetStream منتشر کن و آن‌ها را منتشرشده علامت بزن. یک تراکنش دور کل دسته است:

```go
rows, _ := tx.Query(ctx, `SELECT id, aggregate, type, payload FROM outbox
    WHERE published_at IS NULL ORDER BY id LIMIT $1 FOR UPDATE SKIP LOCKED`, n)
// ... collect the batch, then for each row:
ack, err := js.Publish(r.aggregate+"s."+r.typ, r.payload,
    nats.MsgId("outbox-"+strconv.FormatInt(r.id, 10)))
// ... after the loop:
tx.Exec(ctx, `UPDATE outbox SET published_at = now() WHERE id = ANY($1)`, ids)
```

دو نکته توضیح می‌خواهد. `FOR UPDATE` ردیف‌های انتخاب‌شده را تا پایان تراکنش قفل می‌کند. `SKIP LOCKED` به Postgres می‌گوید: اگر بعضی از آن ردیف‌ها را کس دیگری قفل کرده، منتظرشان نمان و رد شو. همین باعث می‌شود چند relay روی یک جدول کار کنند بی‌آنکه همدیگر را بلاک کنند یا ردیف‌های یکسان بردارند. و `nats.MsgId(...)` هدر `Nats-Msg-Id` را برابر شناسه‌ی ردیف outbox می‌گذارد. JetStream شناسه‌ی پیام‌های اخیر را به خاطر می‌سپارد و اگر همان شناسه را دو بار در پنجره‌ی تشخیص تکراری‌اش ببیند، دومی را ذخیره نمی‌کند و با `Duplicate=true` جواب می‌دهد. چرا به این نیاز داریم را همین الان می‌گویم. در دمو حلقه دسته‌های ۱۰ ردیفی می‌گیرد و تا وقتی چیزی نمانده ادامه می‌دهد.

به ترتیب کارها دقت کنید: اول منتشر کن، بعد علامت بزن. اگر relay بین این دو بمیرد، ردیف منتشرنشده می‌ماند و دوباره فرستاده می‌شود. پس تحویل **at least once** (دست‌کم یک بار) است: رویداد هرگز گم نمی‌شود، اما ممکن است بیش از یک بار فرستاده شود. این را عمداً با `os.Exit(1)` درست بعد از انتشار (پیش از `UPDATE`) ساختم و بعد یک relay سالم راه انداختم:

```
[2105] CRASH after publishing 1 event(s), before marking them
[2107] orders=[o-a,o-c2] outbox rows=1 unpublished=1 stream messages=2
[2109] outbox id=2: PubAck Duplicate=true (stream seq 2)
[2109] relay R2: published=1 duplicates=1
[2111] orders=[o-a,o-c2] outbox rows=1 unpublished=0 stream messages=2
```

خط به خط. relay اول رویداد را منتشر کرد و مُرد. گزارش بعدش `stream messages=2` (رویداد یتیم قبلی به‌علاوه‌ی رویداد جدید) ولی `unpublished=1` را نشان می‌دهد: تراکنش rollback شد، پس دیتابیس هنوز فکر می‌کند ردیف هرگز فرستاده نشده. relay دوم همان ردیف را دوباره، با همان شناسه‌ی پیام، منتشر می‌کند و JetStream با `Duplicate=true` جواب می‌دهد. گزارش آخر `unpublished=0` و باز هم `stream messages=2` را نشان می‌دهد، پس stream یک نسخه از رویداد دارد.

این محافظت حد دارد. تشخیص تکراری JetStream شناسه‌ها را فقط در یک بازه‌ی زمانی به خاطر می‌سپارد (من ۵ دقیقه گذاشتم)، پس تکراری که دیرتر برسد رد می‌شود. برای همین مصرف‌کننده‌های رویداد باید به هر حال idempotent باشند، یعنی رسیدگی به یک رویداد دو بار همان اثر رسیدگی یک بار را داشته باشد ({{< term "idempotency" "idempotency" >}}، مثل نوشته‌ی idempotency). مصرف‌کننده‌ی دموی من روی `Nats-Msg-Id` کلید می‌زند و `applied=2 skipped=0` گزارش کرد: اینجا چیزی برای رد کردن نداشت، چون stream تکراری را خودش حذف کرده بود.

## دو relay هم‌زمان

یک relay نقطه‌ی شکست یگانه است، پس شاید بخواهید دو تا داشته باشید. ۲۰۰ سفارش ساختم و دو پروسه‌ی relay را هم‌زمان راه انداختم:

```
[3412] relay A: published=100 duplicates=0
[3413] relay B: published=100 duplicates=0
[3416] orders=[202 orders] outbox rows=201 unpublished=0 stream messages=202
```

هر relay صد رویداد منتشر کرد و هیچ‌کدام تکراری ندید. این کار `SKIP LOCKED` است: سر ردیف‌های یکسان با هم درگیر نشدند. (تقسیم ۱۰۰/۱۰۰ همان است که این اجرا داد و فرق می‌کند.) stream ۲۰۲ پیام دارد: این ۲۰۰ تا به‌علاوه‌ی دو تا از آزمایش‌های قبلی. outbox ۲۰۱ ردیف دارد، چون اولین سفارشِ آزمایش crash ردیفی باقی نگذاشت.

## پاکسازی

ردیف‌های منتشرشده بار اضافه‌اند. یک `DELETE FROM outbox WHERE published_at < now() - interval '7 days'` دوره‌ای آن‌ها را پاک می‌کند. برای آزمودنش چند ردیف منتشرشده را عقب‌تاریخ‌گذاری کردم و delete را اجرا کردم که ۹۹ ردیف پاک کرد. اگر می‌خواهید debug یا replay کنید ردیف‌ها را چند روز نگه دارید.

## هزینه‌های پنهان outbox

- **ترتیب.** دو relay ممکن است رویدادهای یک aggregate را نامرتب منتشر کنند، چون دسته‌های متفاوتی برمی‌دارند. حتی یک relay فقط ترتیب `id` را دنبال می‌کند و `id` از نوع `bigserial` وقتی تراکنش‌ها هم‌پوشانی دارند ترتیب commit نیست. اگر ترتیب مهم است، برای هر شارد از `aggregate_id` یک relay اجرا کنید، یا با گذاشتن یک نسخه در payload کاری کنید که مصرف‌کننده‌ها نامرتبی را تحمل کنند.
- **relay هنگام صحبت با NATS یک تراکنش (و قفل ردیف) نگه می‌دارد.** دسته‌ها را کوچک نگه دارید و برای انتشار timeout بگذارید، وگرنه یک broker کند ردیف‌ها را قفل نگه می‌دارد.
- **`bigserial` حفره دارد.** create ناموفقِ بالا شناسه‌ی ۱ را مصرف کرد، پس اولین رویداد واقعی شناسه‌ی ۲ گرفت. هرگز شناسه‌ها را «بدون حفره» فرض نکنید.
- **polling بسته به فاصله‌اش یا تأخیر می‌آورد یا بار.** `LISTEN/NOTIFY` در Postgres می‌تواند relay را زودتر بیدار کند، اما اینجا امتحانش نکردم. به هر حال polling را به‌عنوان پشتیبان نگه دارید.
- **relay یک worker مثل بقیه است.** هنگام خاموش‌شدن تمیز متوقفش کنید، مثل [graceful shutdown و workerها](/fa/posts/go-graceful-shutdown-workers/). اگر وسط یک دسته کشته شود، تراکنش rollback می‌شود و ردیف‌ها دوباره تلاش می‌شوند.
- **جدول بزرگ می‌شود.** به کار پاکسازی و همان index جزئی نیاز دارد.

## قدم بعدی

نوشته‌ی بعد «سرویس gRPC با Go» است. رویدادها حالا قابل‌اعتماد از سرویس بیرون می‌روند، اما بعضی فراخواننده‌ها همین الان جواب می‌خواهند، پس سرویس `orders` در دومی برای فراخوانی‌هایی که منتظر جواب می‌مانند و با یک قرارداد نوع‌دار باز می‌شود. (آن دمو store درون‌حافظه‌ای دارد و به outbox وصل نیست.)
