+++
date = '2027-01-23T10:00:00+03:30'
draft = false
title = 'دیتابیس با SQLx در Rust'
description = 'کار با Postgres در Rust با SQLx: PgPool، query_as و FromRow، پارامتر bind، تراکنش با rollback خودکار، migration توکار و query‌های بررسی‌شده هنگام کامپایل.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "sqlx", "postgres", "database", "backend"]
cover = { image = "/images/covers/rust-database-sqlx.fa.png", alt = "دیتابیس با SQLx در Rust", hiddenInSingle = true }
+++

جدول `orders` شما ستونی به نام `cents bigint` دارد. در struct ‏Rust می‌نویسید `cents: i32`. یا نام یک ستون را در query غلط می‌نویسید، `custmer` به‌جای `customer`. کِی می‌فهمید؟ در بیشتر کتابخانه‌های پایگاه داده جواب این است: «وقتی همان خط اجرا شود»، که ممکن است در production باشد و روی مسیری که کم‌تر صدا زده می‌شود. SQLx به شما انتخاب می‌دهد: query‌های ساده موقع اجرا بررسی می‌شوند و ماکروهای `query!` آن‌ها را *همان موقع کامپایل* بررسی می‌کنند.

این مقاله ذخیره‌گاه درون‌حافظه‌ی [API سفارش‌ها با Axum](/fa/posts/rust-http-axum-api/) را با Postgres عوض می‌کند. برای demo یک `OrderStore` کوچک نوشته‌ام: یک struct که یک connection pool نگه می‌دارد و متدهای `create` و `get` و `find` و `list` و یک متد با transaction دارد. اینجا مستقل است؛ مثل قبل می‌توانید آن را به‌عنوان state مشترک به Axum وصل کنید. کتابخانه **SQLx** است، یک ابزار async برای SQL. ORM نیست (ORM کتابخانه‌ای است که SQL را پشت شیءها پنهان می‌کند): SQL را خودتان می‌نویسید و SQLx مجموعه‌ی اتصال‌ها، پارامترها و نگاشت ردیف‌ها به مقدارهای Rust را سامان می‌دهد. هم‌ارز Go این است: [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/).

> از Rust نسخه‌ی 1.90، `sqlx` نسخه‌ی 0.8.6 (با featureهای `runtime-tokio` و `postgres` و `migrate` و `macros`) و `tokio` نسخه‌ی 1.54.1 استفاده کرده‌ام، روی یک PostgreSQL ‏18.3 واقعی که یک launcher کوچک Go با `embedded-postgres` (بدون Docker) روی یک پورت محلی تصادفی بالا آورد و بعد از کار خاموش شد. برای این نسخه‌ی مقاله همه‌ی demoها را دوباره اجرا کردم و خروجی‌ها یکی است. در اجرای اولیه‌ام تازه‌ترین sqlx روی crates.io، یعنی 0.9.0، حداقل نسخه‌ی rustc را 1.94 اعلام کرده بود و Cargo آن را روی 1.90 من رد کرد، پس 0.8 را قفل کردم.

## جدول‌ها

demo دو جدول دارد که با دو فایل migration شماره‌دار ساخته می‌شوند (درباره‌ی migration پایین‌تر می‌گویم):

```sql
CREATE TABLE orders (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer text   NOT NULL,
    cents    bigint NOT NULL CHECK (cents > 0),
    status   text   NOT NULL DEFAULT 'new'
);
CREATE TABLE order_events (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders (id),
    kind     text   NOT NULL
);
```

خود پایگاه داده ردیف‌ها را شماره می‌زند (`GENERATED ALWAYS AS IDENTITY`)، سفارشی با `cents <= 0` را رد می‌کند (همان `CHECK`)، و هر event باید به یک سفارش موجود اشاره کند (`REFERENCES`). این قاعده‌ها را یادتان بماند؛ demo عمداً به بعضی‌شان برخورد می‌کند.

## pool، یک query و نوع ردیف

باز کردن اتصال به پایگاه داده کند است، برای همین سرویس چند اتصال را باز نگه می‌دارد و به درخواست‌ها قرض می‌دهد. این مجموعه‌ی اتصال‌ها یک {{< term "connection-pool" "connection pool" >}} است. `PgPoolOptions` آن را تنظیم می‌کند و `PgPool` که برمی‌گردد یک دستگیره‌ی ارزان و قابل‌کلون به pool مشترک است. برای همین `OrderStore` می‌تواند ساده `#[derive(Clone)]` باشد:

```rust
let pool = PgPoolOptions::new()
    .max_connections(5)
    .acquire_timeout(Duration::from_secs(3))
    .connect(url)
    .await?;
```

حداکثر پنج اتصال باز است و درخواستی که بیش از سه ثانیه منتظر اتصال بماند به‌جای انتظار بی‌پایان خطا می‌گیرد.

حالا یک query. `query_as` یک SQL را اجرا می‌کند و هر ردیف را به structی می‌نگارد که `FromRow` را derive کرده؛ ستون‌ها *با نام* به فیلدها وصل می‌شوند. مقدارها با `.bind()` به جای‌نگه‌دارهای `$1` و `$2` می‌روند و هرگز داخل متن SQL نمی‌روند. این یک {{< term "parameterized-query" "query پارامتری" >}} است: پایگاه داده SQL و مقدارها را جدا می‌گیرد، پس مقدار هیچ‌وقت با SQL اشتباه گرفته نمی‌شود.

```rust
#[derive(Debug, sqlx::FromRow)]
pub struct Order { pub id: i64, pub customer: String, pub cents: i64, pub status: String }

sqlx::query_as::<_, Order>("INSERT INTO orders (customer, cents) VALUES ($1, $2)
                            RETURNING id, customer, cents, status")
    .bind(customer).bind(cents)
    .fetch_one(&self.pool).await
```

`RETURNING` باعث می‌شود Postgres ردیف درج‌شده را، با `id` و `status` پیش‌فرضی که خودش ساخته، پس بفرستد؛ پس با یک رفت‌وبرگشت هم می‌سازیم هم می‌خوانیم. فراخوانی آخر می‌گوید چند ردیف انتظار دارید:

- `fetch_one`: دقیقاً یک ردیف، وگرنه خطا.
- `fetch_optional`: صفر یا یک ردیف، به‌شکل `Option`.
- `fetch_all`: هر تعداد ردیف، به‌شکل `Vec`.

وقتی `fetch_one` چیزی پیدا نکند `sqlx::Error::RowNotFound` برمی‌گرداند. نبودن یک سفارش وضعیت عادی است، نه خرابی پایگاه داده؛ پس آن را به خطای خودم ترجمه می‌کنم تا فراخواننده‌ها هرگز لازم نباشد نوع‌های SQLx را بشناسند:

```rust
.fetch_one(&self.pool).await.map_err(|e| match e {
    sqlx::Error::RowNotFound => StoreError::NotFound(id),
    other => StoreError::Db(other),
})
```

`StoreError` یک enum دست‌نویس است، با پیاده‌سازی‌های `Display` و `Error` و `From<sqlx::Error>`. برای دو variant کد تکراری زیادی است؛ مقاله‌ی بعد جایش را می‌گیرد.

## transaction و rollback هنگام drop

گاهی دو دستور باید با هم موفق یا با هم ناموفق شوند: اینجا درج یک سفارش و نوشتن یک event حسابرسی درباره‌ی آن. یک {{< term "transaction" "transaction" >}} همین قول را می‌دهد. `pool.begin()` یکی شروع می‌کند و یک `Transaction` برمی‌گرداند. query‌ها را به‌جای pool روی `&mut *tx` اجرا می‌کنید و با `commit()` تمام می‌کنید. اگر transaction بدون commit drop شود، SQLx آن را rollback می‌کند. یعنی `return` زودهنگام یا `?` وسط کار بی‌خطر است:

```rust
let mut tx = self.pool.begin().await?;
let (id,): (i64,) = sqlx::query_as("INSERT INTO orders (customer, cents) VALUES ($1, $2) RETURNING id")
    .bind(customer).bind(cents).fetch_one(&mut *tx).await?;
if fail_after_insert {
    return Err(StoreError::NotFound(-1)); // tx اینجا drop می‌شود، هرگز commit نشده
}
sqlx::query("INSERT INTO order_events (order_id, kind) VALUES ($1, 'created')")
    .bind(id).execute(&mut *tx).await?;
tx.commit().await?;
```

پرچم `fail_after_insert` فقط برای demo است: درست بعد از درج اول خطا برمی‌گرداند، به‌جای هر شکست دیگری، تا rollback را ببینیم.

## migration‌ها و یک اجرای کامل

**migration** یک فایل `.sql` شماره‌دار است که schema را تغییر می‌دهد؛ فایل‌ها به ترتیب و هر کدام فقط یک بار اجرا می‌شوند. آن‌ها را در پوشه‌ی `migrations/` بگذارید و `sqlx::migrate!("./migrations").run(&pool).await?` فایل‌ها را داخل باینری می‌گذارد و آن‌هایی را که مانده اجرا می‌کند. SQLx آنچه اجرا کرده را در جدولی به نام `_sqlx_migrations` به یاد می‌سپارد.

`main` در demo برای `alice` یک سفارش می‌سازد، سفارش‌هایش را فهرست می‌کند، idای را که وجود ندارد می‌جوید، سفارشی با `cents` منفی را امتحان می‌کند، یک transaction موفق و یک transaction که drop می‌شود اجرا می‌کند و آخر جدول migration را چاپ می‌کند. خروجی‌اش این است:

```text
created: Order { id: 1, customer: "alice", cents: 1500, status: "new" }
alice has 2 orders
get(999)  -> order 999 not found
find(999) -> None
bad cents -> database error: error returned from database: new row for relation "orders" violates check constraint "orders_cents_check"
count before tx tests: 2
committed tx, new id 4, count: 3
failing tx -> order -1 not found
count after dropped tx: 3
migration 1 create orders success=true
migration 2 create order events success=true
```

خط به خط:

- دو خط اول درج با `RETURNING` و سفارش دوم alice است، پس `list` دو سفارش پیدا می‌کند.
- `get(999)` از `fetch_one` استفاده می‌کند، پس ردیف نبوده می‌شود خطای `NotFound` خودمان. `find(999)` برای همان id از `fetch_optional` استفاده می‌کند و `None` می‌گیرد. یک query، دو راه پرسیدن.
- `bad cents` قاعده‌ی `CHECK (cents > 0)` در عمل است. پایگاه داده ردیف را رد کرد و خطایی که می‌بینیم پیام خود پایگاه داده است که داخل variant ‏`Db` ما پیچیده شده. این پایگاه داده است که قاعده را اعمال می‌کند، نه کد Rust ما.
- بعد transaction‌ها. آن که commit شد یک سفارش و eventش را درج کرد و شمار از ۲ به ۳ رسید. آن که شکست خورد یک ردیف درج کرد و بعد زود برگشت؛ بعدش شمار هنوز ۳ است، پس درج رهاشده rollback شد.
- سفارش commit‌شده id ‏۴ دارد، نه ۳. درج ردشده‌ی `bob` هیچ‌وقت ردیف نشد ولی یک شماره‌ی identity را مصرف کرد. انتظار id بدون فاصله نداشته باشید.
- دو خط آخر مستقیم از `_sqlx_migrations` می‌آید: هر دو migration با موفقیت اجرا شده‌اند.

## query‌های بررسی‌شده در زمان کامپایل

هر چه تا اینجا دیدیم SQL را موقع *اجرا* بررسی می‌کند: غلط‌املایی در نام ستون همان لحظه شکست می‌خورد. ماکروهای `query!` و `query_as!` کار غیرمعمولی می‌کنند. موقع کامپایل به پایگاه داده وصل می‌شوند (نشانی از متغیر محیطی `DATABASE_URL` می‌آید)، از آن می‌خواهند query را تحلیل کند، و SQL و نوع‌های Rust شما را با schema واقعی می‌سنجند. پوشه‌ی `checked` در demo یک query از این نوع دارد، `SELECT id, customer, cents FROM orders WHERE cents >= $1`، و اجرایش می‌کند:

```text
Order { id: 1, customer: "alice", cents: 1500 }
Order { id: 2, customer: "alice", cents: 700 }
```

سه برنامه که قرار است شکست بخورند نشان می‌دهند چه به دست می‌آورید. اول، نام ستونی که غلط نوشته شده:

```text
error: error returned from database: column "custmer" does not exist
  --> src/bin/bad_column.rs:13:18
   |
13 |     let orders = sqlx::query_as!(Order, "SELECT id, custmer, cents FROM orders")
```

اشتباه یک خطای کامپایل است، با پیام خود پایگاه داده و خط دقیق. دوم، struct با `cents: i32` برای ستون `bigint` در type checker شکست می‌خورد با `the trait bound i32: From<i64> is not satisfied`. سوم، bind کردن یک `&str` به `WHERE id = $1` که `id` از نوع `bigint` است می‌دهد `expected i64, found &str`. (خروجی کامپایلر نوع‌های دیگری را هم که `From` دارند فهرست می‌کند؛ آن را حذف کرده‌ام.)

بهایش این است که ماکروها موقع build به پایگاه داده نیاز دارند. بدون `DATABASE_URL` این را می‌گیرید:

```text
error: set `DATABASE_URL` to use query macros online, or run `cargo sqlx prepare` to update the query cache
```

پیام راه خروج را هم می‌گوید. برای build‌های CI و Docker که پایگاه داده ندارند، `cargo sqlx prepare` (از ابزار `sqlx-cli`) بررسی‌ها را یک بار اجرا می‌کند و پوشه‌ی `.sqlx/` از فایل‌های JSON کوچک می‌نویسد، با متن هر query و نوع ستون‌ها و nullability؛ آن را commit می‌کنید. `.sqlx/` در demo برای تنها query ما یک فایل دارد. `checked` را دوباره با `DATABASE_URL` تنظیم‌نشده و با وجود آن پوشه ساختم و کامپایل شد؛ با پوشه‌ی کنار گذاشته‌شده همان خطای بالا آمد. در اجرای اولیه‌ام `sqlx-cli` نسخه‌ی 0.8.6 را در یک پوشه‌ی خصوصی نصب کردم (build‌اش چند دقیقه طول کشید) و خودم `cargo sqlx prepare` را اجرا کردم؛ آنجا دیدم تغییر متن query بدون prepare دوباره خطا را برمی‌گرداند. در این اجرای مجدد مرحله‌ی `prepare` را تکرار نکردم و از cache‌ای که commit شده بود استفاده کردم.

## مقایسه با pgx و sqlc در Go

هر دو اکوسیستم SQL را همان SQL نگه می‌دارند. راه معمول در Go ابزار sqlc است: schema و query‌های شما را می‌خواند و کد Go را از پیش *تولید می‌کند*، پس کامپایلر Go هر فراخوانی آن کد تولیدشده را بررسی می‌کند و موقع build به پایگاه داده نیازی نیست. ماکروهای SQLx هم موقع کامپایل بررسی می‌کنند ولی در برابر یک پایگاه داده‌ی زنده یا cache ‏`.sqlx` که commit شده. هم `sqlx::query_as` ساده و هم `Query` در pgx بدون بررسی‌اند: غلط‌املایی وقتی query اجرا شود شکست می‌خورد.

## تله‌های کار با پایگاه داده

- **فهرست صریح ستون‌ها را به `SELECT *` ترجیح بدهید.** `FromRow` با نام تطبیق می‌دهد، پس ستون اضافه یا تغییرنام‌یافته خطای زمان اجرا می‌شود و `SELECT *` احتمالش را بیشتر می‌کند.
- **`.sqlx/` را commit کنید و در CI دستور `cargo sqlx prepare --check` را اجرا کنید.** وگرنه cache کهنه می‌شود و build بسته به حضور یا غیاب پایگاه داده موفق یا ناموفق می‌شود.
- **یک `Transaction` را در کار کندِ غیرپایگاهی نگه ندارید.** در تمام آن مدت یک اتصال از pool را اشغال می‌کند.
- **درج rollback‌شده هم شماره‌ی identity مصرف می‌کند.** id بدون فاصله انتظار نداشته باشید و هرگز با آن ردیف‌ها را نشمارید.

## تمرین

۱. متد `mark_paid(id)` را اضافه کنید که از `UPDATE ... WHERE id = $1 AND status = 'new'` استفاده می‌کند و وقتی هیچ ردیفی تغییر نکرد `NotFound` برمی‌گرداند (راهنما: `execute` نتیجه‌ای با `rows_affected()` برمی‌گرداند).
۲. یک migration سوم بنویسید که ستون `created_at timestamptz NOT NULL DEFAULT now()` را اضافه کند و بعدش جدول `_sqlx_migrations` را ببینید.

## قدم بعدی

`StoreError` ما برای دو variant کد دست‌نویس تکراری زیادی دارد. مقاله‌ی بعد، «خطا در اپلیکیشن واقعی: thiserror و anyhow»، آن را از بین می‌برد.
