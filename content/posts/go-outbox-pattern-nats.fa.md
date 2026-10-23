+++
date = '2027-01-31T10:00:00+03:30'
draft = false
title = 'Outbox Pattern با Postgres و NATS در Go'
description = 'مشکل dual write را در Go حل می‌کنیم: جدول outbox در همان transaction، یک relay با SKIP LOCKED که در JetStream منتشر می‌کند، و اجرای واقعی crash.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "outbox", "postgres", "nats", "jetstream", "transactions"]
cover = { image = "/images/covers/go-outbox-pattern-nats.fa.png", alt = "Outbox Pattern با Postgres و NATS در Go", hiddenInSingle = true, hiddenInList = true }
+++

بعد از [الگوهای concurrency در Go](/fa/posts/go-concurrency-patterns/) ابزار اجرای حلقه‌های پس‌زمینه را داریم. یک کار کلاسیک برای آن‌ها خبر دادن به بقیه‌ی سیستم است که چیزی اتفاق افتاده. وقتی سفارشی ذخیره می‌شود، سرویس‌های دیگر event با نام `order.created` می‌خواهند. ذخیره در Postgres و انتشار در NATS دو سیستم جدا هستند و هیچ transaction‌ای هر دو را پوشش نمی‌دهد. این همان **dual write problem** است و **outbox pattern** جواب استانداردش. این‌جا روی جدول سفارش‌ها از [Postgres با pgx و sqlc](/fa/posts/go-postgres-pgx-sqlc/) و ایده‌ی transaction از [الگوهای transaction در Go](/fa/posts/go-transactions-patterns/) سوار می‌شوم و برای انتشار از dedup مقاله‌ی [idempotency در JetStream](/fa/posts/nats-jetstream-idempotency/) استفاده می‌کنم.

> همه‌چیز با Go 1.26 روی یک PostgreSQL 18.3 واقعی (embedded-postgres نسخه‌ی v1.34.0 و pgx نسخه‌ی v5.11.0) و یک nats-server نسخه‌ی v2.15.1 توکار با nats.go نسخه‌ی v1.54.0 اجرا شده است. هر مرحله یک process جداست، پس crash یک `os.Exit(1)` واقعی است. ماشین مشغول بود (load average بین ۴ تا ۱۰)، برای همین ادعایی درباره‌ی زمان نمی‌کنم.

## شکست، این بار واقعی

اول در دیتابیس بنویس، بعد منتشر کن. process بین این دو می‌میرد:

```go
pool.Exec(ctx, `INSERT INTO orders (id, customer, cents) VALUES ('o-a', 'ali', 1500)`)
os.Exit(1) // crash here
js.Publish("orders.created", []byte(`{"order_id":"o-a"}`))
```

```
[2089] order o-a committed
[2091] orders=[o-a] outbox rows=0 unpublished=0 stream messages=0
```

سفارش هست و هیچ‌کس هیچ‌وقت خبردار نمی‌شود. ترتیب را برعکس کنید: اول منتشر کن، بعد بنویس، با نوشتنی که در دیتابیس شکست می‌خورد:

```
[2093] event for o-b published
[2093] insert o-b: ERROR: new row for relation "orders" violates check constraint "orders_cents_check" (SQLSTATE 23514)
[2095] orders=[o-a] outbox rows=0 unpublished=0 stream messages=1
[2095]   stream seq 1: {"order_id":"o-b"}
```

حالا event برای سفارشی وجود دارد که اصلاً نیست. retry هیچ‌کدام را درست نمی‌کند، چون crash حافظه‌ی retry را هم با خودش می‌برد.

## جدول outbox

به‌جای انتشار، سرویس event را به شکل یک ردیف می‌نویسد، آن هم در همان transaction ردیف کسب‌وکار. Postgres تضمین می‌کند هر دو commit شوند یا هیچ‌کدام:

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

تابع `withTx` یک helper کوچک خودم دور `pgx.BeginFunc` است (با nil، commit؛ با error، rollback):

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

یک بار process را درست قبل از commit کشتم و بعد عادی اجرا کردم:

```
[2097] CRASH before commit
[2099] orders=[o-a] outbox rows=0 unpublished=0 stream messages=1
[2103] orders=[o-a,o-c2] outbox rows=1 unpublished=1 stream messages=1
```

سفارشی که crash کرد هیچ ردی نگذاشت، نه سفارش و نه event. سفارش موفق هر دو را گذاشت و event منتظر انتشار است.

## relay

یک حلقه‌ی جدا ردیف‌های منتشرنشده را می‌خواند، منتشر می‌کند و علامت می‌زند. یک transaction دور کل batch است:

```go
rows, _ := tx.Query(ctx, `SELECT id, aggregate, type, payload FROM outbox
    WHERE published_at IS NULL ORDER BY id LIMIT $1 FOR UPDATE SKIP LOCKED`, n)
// ... collect the batch, then for each row:
ack, err := js.Publish(r.aggregate+"s."+r.typ, r.payload,
    nats.MsgId("outbox-"+strconv.FormatInt(r.id, 10)))
// ... after the loop:
tx.Exec(ctx, `UPDATE outbox SET published_at = now() WHERE id = ANY($1)`, ids)
```

`FOR UPDATE` ردیف‌ها را قفل می‌کند و `SKIP LOCKED` باعث می‌شود relay دوم به‌جای منتظر ماندن، ردیف‌های قفل‌شده را رد کند. مقدار `Nats-Msg-Id` همان id در outbox است، پس انتشار تکراری اثری ندارد.

تحویل **at least once** است: relay می‌تواند منتشر کند و قبل از `UPDATE` بمیرد. این را با `os.Exit(1)` بعد از انتشار شبیه‌سازی کردم و بعد یک relay سالم بالا آوردم:

```
[2105] CRASH after publishing 1 event(s), before marking them
[2107] orders=[o-a,o-c2] outbox rows=1 unpublished=1 stream messages=2
[2109] outbox id=2: PubAck Duplicate=true (stream seq 2)
[2109] relay R2: published=1 duplicates=1
[2111] orders=[o-a,o-c2] outbox rows=1 unpublished=0 stream messages=2
```

ردیف منتشرنشده ماند (transaction برگشت خورد)، relay دوم دوباره منتشرش کرد و JetStream جواب `Duplicate=true` داد. stream هنوز فقط یک نسخه دارد. پنجره‌ی dedup محدود است (من ۵ دقیقه گذاشتم)، پس consumer‌ها همچنان باید idempotent باشند، مثل مقاله‌ی idempotency. consumer دمو بر اساس `Nats-Msg-Id` کار می‌کند و `applied=2 skipped=0` گزارش داد، چون داخل پنجره، خود stream تکراری را حذف کرده بود.

## دو relay هم‌زمان

۲۰۰ سفارش seed کردم و دو process از relay را هم‌زمان اجرا کردم:

```
[3412] relay A: published=100 duplicates=0
[3413] relay B: published=100 duplicates=0
[3416] orders=[202 orders] outbox rows=201 unpublished=0 stream messages=202
```

۱۰۰ بعلاوه‌ی ۱۰۰ می‌شود ۲۰۰ و هیچ‌کدام تکراری ندیدند. (تقسیم ۱۰۰/۱۰۰ نتیجه‌ی همین اجراست و در اجراهای دیگر فرق می‌کند.) stream هم ۲۰۲ پیام دارد: همین ۲۰۰ تا و دو تای قبلی.

## پاک‌سازی

ردیف‌های منتشرشده بعد از مدتی فقط جا می‌گیرند. یک `DELETE FROM outbox WHERE published_at < now() - interval '7 days'` دوره‌ای آن‌ها را پاک می‌کند؛ چند ردیف را قدیمی نشان دادم و ۹۹ ردیف حذف شد. اگر برای debug یا replay لازم دارید، چند روز نگهشان دارید.

## چند نکته که باید حواستان باشد

- **ترتیب.** دو relay می‌توانند event‌های یک aggregate را جابه‌جا منتشر کنند، چون batch‌های متفاوتی برمی‌دارند. حتی یک relay هم فقط ترتیب `id` را دنبال می‌کند و `id` از نوع bigserial وقتی transaction‌ها هم‌پوشانی دارند، ترتیب commit نیست. اگر ترتیب مهم است، برای هر شارد از `aggregate_id` یک relay بگذارید، یا یک version در payload بگذارید تا consumer جابه‌جایی را تحمل کند.
- relay هنگام حرف زدن با NATS یک transaction و قفل ردیف‌ها را نگه می‌دارد. batch را کوچک نگه دارید و روی انتشار timeout بگذارید.
- `bigserial` سوراخ دارد: create که crash کرد id شماره‌ی ۱ را مصرف کرد و اولین event واقعی id شماره‌ی ۲ گرفت.
- polling بسته به فاصله‌اش یا تأخیر می‌آورد یا بار. `LISTEN/NOTIFY` در Postgres می‌تواند relay را زودتر بیدار کند، ولی این‌جا آزمایشش نکردم؛ polling را به‌عنوان پشتیبان نگه دارید.
- relay هم یک worker معمولی است: هنگام خاموش‌شدن تمیز متوقفش کنید، مثل [graceful shutdown و workerها](/fa/posts/go-graceful-shutdown-workers/). اگر وسط batch کشته شود، transaction برمی‌گردد و ردیف‌ها دوباره تلاش می‌شوند.
- جدولی که بزرگ می‌شود به job پاک‌سازی و همان index جزئی نیاز دارد.

## قدم بعدی

در مقاله‌ی بعد یک سرویس gRPC در Go می‌سازیم.
