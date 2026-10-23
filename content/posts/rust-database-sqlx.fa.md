+++
date = '2027-01-23T10:00:00+03:30'
draft = false
title = 'دیتابیس با SQLx در Rust'
description = 'کار با Postgres در Rust با SQLx: PgPool، query_as و FromRow، پارامتر bind، تراکنش با rollback خودکار، migration توکار و query‌های بررسی‌شده هنگام کامپایل.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "sqlx", "postgres", "database", "backend"]
cover = { image = "/images/covers/rust-database-sqlx.fa.png", alt = "دیتابیس با SQLx در Rust", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-http-axum-api/) یک API سفارش‌ها با Axum ساختیم که همه‌چیز را در حافظه نگه می‌داشت. این مقاله آن را با Postgres عوض می‌کند. برای این دمو یک `OrderStore` کوچک نوشتم: struct‌ای که یک connection pool دارد و متدهای `create`، `get`، `find`، `list` و یک متد تراکنشی. مستقل است و مثل قبل به‌عنوان state مشترک به Axum داده می‌شود. از **SQLx** استفاده می‌کنم؛ ابزار async برای SQL که ORM نیست: SQL را خودتان می‌نویسید و pool، پارامتر و تبدیل ردیف به struct با خود SQLx است. معادل Go در [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/) آمده است.

> Rust نسخه‌ی 1.90، `sqlx` نسخه‌ی 0.8.6 (با featureهای `runtime-tokio`، `postgres`، `migrate` و `macros`) و `tokio` نسخه‌ی 1.54.1، روی PostgreSQL 18.3 واقعی که یک launcher کوچک Go با `embedded-postgres` بالا آورد (بدون Docker) و آخر کار خاموشش کردم. جدیدترین sqlx روی crates.io یعنی 0.9.0 حداقل rustc 1.94 می‌خواهد و Cargo آن را روی 1.90 من نپذیرفت، پس نسخه‌ی 0.8 را pin کردم.

## Pool، ردیف‌ها و پارامترها

`PgPoolOptions` **connection pool** را تنظیم می‌کند. `PgPool` یک handle سبک و قابل clone است، برای همین store می‌تواند `#[derive(Clone)]` باشد.

```rust
let pool = PgPoolOptions::new()
    .max_connections(5)
    .acquire_timeout(Duration::from_secs(3))
    .connect(url)
    .await?;
```

`query_as` ردیف‌ها را به structی تبدیل می‌کند که `FromRow` derive کرده است (ستون‌ها با نام تطبیق داده می‌شوند). مقدارها با `.bind()` و برای `$1` و `$2` می‌آیند، نه داخل رشته‌ی SQL:

```rust
#[derive(Debug, sqlx::FromRow)]
pub struct Order { pub id: i64, pub customer: String, pub cents: i64, pub status: String }

sqlx::query_as::<_, Order>("INSERT INTO orders (customer, cents) VALUES ($1, $2)
                            RETURNING id, customer, cents, status")
    .bind(customer).bind(cents)
    .fetch_one(&self.pool).await
```

متد fetch مشخص می‌کند چند ردیف انتظار دارید: `fetch_one` (دقیقاً یکی، وگرنه `Err`)، `fetch_optional` (یک `Option`) و `fetch_all` (یک `Vec`). وقتی `fetch_one` چیزی پیدا نکند `sqlx::Error::RowNotFound` برمی‌گرداند. من آن را به خطای دامنه تبدیل می‌کنم تا برای حالت عادیِ «پیدا نشد» نوع‌های SQLx به بیرون نشت نکنند:

```rust
.fetch_one(&self.pool).await.map_err(|e| match e {
    sqlx::Error::RowNotFound => StoreError::NotFound(id),
    other => StoreError::Db(other),
})
```

`StoreError` یک enum دست‌نویس با `Display`، `Error` و `From<sqlx::Error>` است؛ مقاله‌ی بعد این boilerplate را کنار می‌گذارد.

## تراکنش و rollback هنگام drop

`pool.begin()` یک `Transaction` می‌دهد. `&mut *tx` را به‌جای executor بدهید و آخر `commit()` را صدا بزنید. اگر تراکنش بدون `commit` drop شود، SQLx آن را rollback می‌کند، پس برگشتن زودهنگام با `?` امن است:

```rust
let mut tx = self.pool.begin().await?;
let (id,): (i64,) = sqlx::query_as("INSERT INTO orders (customer, cents) VALUES ($1, $2) RETURNING id")
    .bind(customer).bind(cents).fetch_one(&mut *tx).await?;
if fail_after_insert {
    return Err(StoreError::NotFound(-1)); // tx dropped here, never committed
}
sqlx::query("INSERT INTO order_events (order_id, kind) VALUES ($1, 'created')")
    .bind(id).execute(&mut *tx).await?;
tx.commit().await?;
```

## Migration توکار

فایل‌های `.sql` شماره‌دار را در `migrations/` بگذارید. `sqlx::migrate!("./migrations").run(&pool).await?` آن‌ها را داخل باینری embed می‌کند و موارد اجرانشده را اعمال می‌کند. SQLx هر کدام را در جدول `_sqlx_migrations` ثبت می‌کند. خروجی یک اجرای کامل دمو:

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

بعد از تراکنش ناموفق تعداد همان ۳ مانده است: insertِ drop‌شده rollback شده. id تراکنش موفق ۴ است نه ۳: insert ردشده‌ی `bob` یک مقدار identity مصرف کرده است.

## query‌هایی که هنگام کامپایل بررسی می‌شوند

ماکروهای `query!` و `query_as!` **هنگام کامپایل** به دیتابیس وصل می‌شوند و SQL را با schema واقعی می‌سنجند. اشتباه تایپی در نام ستون:

```text
error: error returned from database: column "custmer" does not exist
  --> src/bin/bad_column.rs:13:18
   |
13 |     let orders = sqlx::query_as!(Order, "SELECT id, custmer, cents FROM orders")
```

فیلد `cents: i32` برای ستون `bigint` در type checker رد می‌شود (`the trait bound i32: From<i64> is not satisfied`) و bind کردن یک `&str` به `WHERE id = $1` خطای `expected i64, found &str` می‌دهد. این ماکروها هنگام build به `DATABASE_URL` نیاز دارند. بدون آن:

```text
error: set `DATABASE_URL` to use query macros online, or run `cargo sqlx prepare` to update the query cache
```

برای CI و buildهای Docker که دیتابیس ندارند، `cargo sqlx prepare` بررسی‌ها را یک‌بار اجرا می‌کند و پوشه‌ی `.sqlx/` را با فایل‌های JSON می‌نویسد (متن query، نوع ستون‌ها و nullable بودن) که باید commit کنید. من `sqlx-cli` نسخه‌ی 0.8.6 را در یک پوشه‌ی خصوصی نصب کردم (ساختنش چند دقیقه طول کشید)، `cargo sqlx prepare` را زدم و بعد با `DATABASE_URL` تنظیم‌نشده build کردم: کامپایل شد. وقتی متن query را بدون prepare دوباره عوض کردم همان خطای بالا برگشت؛ یعنی cache بر اساس متن دقیق query کار می‌کند.

## مقایسه با pgx و sqlc در Go

هر دو اکوسیستم SQL را SQL نگه می‌دارند. راه معمول در Go مسیر sqlc است: schema و query‌های شما را می‌خواند و از قبل کد Go تولید می‌کند، پس کامپایلر صدا زدن آن کد را بررسی می‌کند و برای build دیتابیس لازم نیست. ماکروهای SQLx هم هنگام کامپایل بررسی می‌کنند، ولی با یک دیتابیس زنده یا cache‌ی `.sqlx` که commit شده. `sqlx::query_as` ساده و `Query` در pgx هر دو بررسی نمی‌شوند: غلط تایپی وقتی query اجرا شود خطا می‌دهد.

## چند نکته که باید حواستان باشد

- لیست ستون‌ها را صریح بنویسید و `SELECT *` نزنید؛ `FromRow` با نام تطبیق می‌دهد و ستون اضافه یا تغییرنام‌یافته در زمان اجرا خطا می‌شود.
- `.sqlx/` را commit کنید و در CI دستور `cargo sqlx prepare --check` را بزنید تا cache کهنه نشود.
- یک `Transaction` را هنگام کارهای کند غیر دیتابیسی باز نگه ندارید؛ یک اتصال pool را اشغال می‌کند.
- insert که rollback شود هم مقدار identity مصرف می‌کند؛ انتظار idهای بدون فاصله نداشته باشید.

## تمرین

1. متد `mark_paid(id)` را بنویسید که از `UPDATE ... WHERE id = $1 AND status = 'new'` استفاده کند و اگر هیچ ردیفی تغییر نکرد `NotFound` بدهد (راهنمایی: `execute` نتیجه‌ای با `rows_affected()` برمی‌گرداند).
2. migration سومی بنویسید که ستون `created_at timestamptz NOT NULL DEFAULT now()` را اضافه کند و `_sqlx_migrations` را ببینید.

## قدم بعدی

`StoreError` ما boilerplate زشتی دارد. در مقاله‌ی بعد: خطا در برنامه‌های واقعی با thiserror و anyhow.
