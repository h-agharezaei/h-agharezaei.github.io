+++
date = '2027-02-11T10:00:00+03:30'
draft = false
title = 'Postgres از Node.js با pg'
description = 'Postgres از Node.js با pg: Pool، پارامتر، غافلگیری نوع‌ها، تراکنش، SQL injection، خطاهای SQLSTATE، timeout و خاموشی تمیز، همه با اجرای واقعی.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "postgres", "pg", "sql", "connection-pool"]
cover = { image = "/images/covers/node-postgres-pg.fa.png", alt = "Postgres از Node.js با pg", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [ساختار پروژه و کانفیگ در Node.js](/fa/posts/node-project-structure-config/)، آدرس دیتابیس از کانفیگ خوانده شد. حالا از آن استفاده می‌کنیم. با `pg` (همان node-postgres) به یک PostgreSQL واقعی وصل می‌شوم و با [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/) مقایسه می‌کنم. helper تراکنش هم شبیه [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/) است.

> Node نسخه‌ی v20.13.1، `pg` نسخه‌ی 8.23.1، `pg-cursor` نسخه‌ی 2.22.1، PostgreSQL نسخه‌ی 18.3 روی loopback و schema مشترک «shop» (customers، orders و...) با چند ردیف. اسکریپت‌ها مثال محلی‌اند و خروجی‌ها واقعی‌اند. زمان‌بندی نگرفته‌ام.

## Pool و query

یک **{{< term "connection-pool" "connection pool" >}}** چند اتصال باز نگه می‌دارد و قرض می‌دهد. `pool.query` یکی را می‌گیرد، SQL را اجرا می‌کند و پس می‌دهد. مقدارها به‌شکل پارامتر (`$1`) می‌روند، نه داخل رشته‌ی SQL:

```js
const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 4 });
const r = await pool.query('SELECT id, name FROM customers WHERE country = $1 ORDER BY id LIMIT $2', ['DE', 2]);
console.log(r.rows, r.rowCount, r.fields.map(f => f.name), r.command);
```

```text
[ { id: '1', name: 'c1' }, { id: '2', name: 'c2' } ] 2 [ 'id', 'name' ] SELECT
```

نتیجه `rows`، `rowCount`، `fields` و `command` دارد. به `id` دقت کنید: رشته‌ی `'1'` است.

## غافلگیری نوع‌ها

چند نوع را در یک query انتخاب کردم:

```text
count   string  30
sum     string  46500
bigint  string  1
numeric string  12.50
int     number  7
now()   Date
```

`bigint`، `numeric`، `count(*)` و `sum` به‌شکل **string** برمی‌گردند. عددهای JavaScript از نوع double هستند و مقدار بزرگ‌تر از 2^53 خراب می‌شود: `9007199254740993::bigint` به‌صورت `'9007199254740993'` رسید و `Number()` آن `9007199254740992` شد. تله‌اش `row.n + 1` است: نتیجه `301` شد، نه `31`. تبدیل را عمدی انجام دهید (`Number(row.n)` وقتی می‌دانید کوچک است، وگرنه `BigInt` یا string، یا در SQL با `count(*)::int`). `timestamptz` به `Date` تبدیل می‌شود و ستون **{{< term "jsonb" "jsonb" >}}** به شیء واقعی parse می‌شود (`meta.tags` برابر `['a', 'b']` بود؛ [JSONB و جست‌وجوی متنی](/fa/posts/db-jsonb-fulltext-search/) را ببینید). pgx در Go مقدار `bigint` را مستقیم در `int64` می‌ریزد؛ اینجا پیش‌فرض امن، string است.

## محدودیت‌های pool

`max: 2` و `connectionTimeoutMillis: 300` گذاشتم، هر دو اتصال را با `pool.connect()` گرفتم و query سوم را زدم:

```text
total/idle/waiting 2 0 0
Error | timeout exceeded when trying to connect
after release 2 2
after idle timeout 0 0
```

pool تمام‌شده فوری خطا نمی‌دهد: query منتظر می‌ماند و بعد از timeout همین خطا پرتاب می‌شود. بدون `connectionTimeoutMillis` (پیش‌فرض: بی‌نهایت صبر) برنامه گیر می‌کند. client نشت‌کرده (بدون `release()`) هم همین شکل را دارد. بعد از release هر دو idle شدند و با `idleTimeoutMillis: 1000` بسته شدند.

## تراکنش با client اختصاصی

یک تراکنش باید روی یک اتصال اجرا شود؛ پس `BEGIN`/`COMMIT` با `pool.query` غلط است، چون هر فراخوانی ممکن است اتصال دیگری بگیرد. یک client بگیرید و همیشه در `finally` آزادش کنید:

```js
async function withTx(fn) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}
```

دو سفارش `paid` commit کردم، بعد تراکنشی اجرا کردم با یک insert معتبر و یک insert با مشتری ناموجود:

```text
paid before 0
after commit 2
inside tx sees 3
failed: 23503 orders_customer_id_fkey
after rollback 2 idle 1 total 1
```

**{{< term "transaction" "تراکنش" >}}** شکست‌خورده ردیف خودش را دید (3) و بعد rollback شد (2). client به pool برگشت.

## SQL injection

همان query را دو جور ساختم. ورودی مهاجم `x' OR '1'='1` است:

```text
concat normal: 1 rows
concat evil  : 6 rows
param  evil  : 0 rows
notes before: notes
after param attack : notes
after concat attack: null
```

با چسباندن رشته، ورودی بد هر 6 مشتری را برگرداند و ورودی `x'; DROP TABLE notes; --` واقعاً جدول دمو را پاک کرد (`null` یعنی دیگر وجود ندارد). با `$1` همان متن فقط کشوری است که وجود ندارد. این **{{< term "sql-injection" "SQL injection" >}}** است. پارامترها جدا از متن SQL می‌روند و نمی‌شود از آن‌ها فرار کرد. نام جدول و ستون پارامتر نمی‌شود؛ از فهرست مجاز استفاده کنید.

## خطا و SQLSTATE

`err.code` همان **{{< term "sqlstate" "SQLSTATE" >}}** و `err.constraint` نام constraint است. یک تابع آن‌ها را به خطای دامنه تبدیل می‌کند، مثل [خطا و unhandled rejection در Node.js](/fa/posts/node-errors-unhandled-rejections/):

```js
function mapPgError(err) {
  switch (err.code) {
    case '23505': return new DomainError('conflict', 'already exists');
    case '23503': return new DomainError('invalid', 'referenced row does not exist');
    case '23514': return new DomainError('invalid', 'value violates a rule');
    default: return err;
  }
}
```

```text
dup email | code 23505 | constraint customers_email_key  -> 409 conflict
bad fk    | code 23503 | constraint orders_customer_id_fkey -> 422 invalid
check     | code 23514 | constraint orders_status_check  -> 422 invalid
syntax    | code 42601 -> unmapped, rethrow
```

کدهای ناشناخته به‌عنوان باگ دوباره پرتاب می‌شوند.

## Timeout و رویداد error در pool

با `statement_timeout: 200` سرور query کند را لغو می‌کند و اتصال قابل استفاده می‌ماند:

```text
statement_timeout: 57014 canceling statement due to statement timeout
pool still works: 1
query_timeout: undefined Query read timeout
```

`query_timeout` فرق دارد: سمت client منصرف می‌شود (بدون SQLSTATE) و به سرور خبر نمی‌رسد. آزمودم: یک اتصال دوم بعد از timeout کلاینت هنوز `select pg_sleep(4)` را با وضعیت `active` و `wait_event = PgSleep` می‌دید. `statement_timeout` را ترجیح دهید.

یک client بیکار می‌تواند بمیرد (با `pg_terminate_backend` کشتمش). بدون handler، pool خطا را دوباره emit می‌کند و Node با `Unhandled 'error' event` (کد 57P01) می‌افتد. با `pool.on('error', ...)` پردازش زنده ماند و pool آن client مرده را کنار گذاشت:

```text
pool error event: 57P01 terminating connection due to administrator command
survived; idle clients: 0
```

## Cursor و خاموشی

برای نتیجه‌ی بزرگ، `pg-cursor` به‌جای بارگذاری همه‌ی ردیف‌ها، دسته‌دسته می‌خواند (سری 25 تایی با اندازه‌ی دسته‌ی 10: `10, 10, 5`). روی client اختصاصی استفاده‌اش کنید.

برای خاموشی، `pool.end()` منتظر clientهای قرض‌گرفته می‌ماند. سروری ساختم که handler آن `pg_sleep(1)` اجرا می‌کرد، یک درخواست فرستادم و بعد `SIGTERM`. پاسخ `42` باز هم رسید، لاگ `closing server, then pool` و `pool ended, exiting` را نشان داد و exit code برابر 0 بود. این همان الگوی [سرور HTTP با node:http](/fa/posts/node-http-server/) است.

## چند نکته‌ی مهم

- همیشه پارامتر؛ هرگز مقدار را به SQL نچسبانید.
- `bigint`، `numeric` و `count(*)` رشته‌اند: عمداً تبدیل کنید.
- برای تراکنش از `pool.connect()` استفاده کنید و `release()` را در `finally` بگذارید.
- `connectionTimeoutMillis`، `statement_timeout` و handler برای `pool.on('error')` را تنظیم کنید.
- روی `err.code` شاخه بزنید، نه روی متن پیام.

## تمرین

تابع `createOrder(customerId, productId, qty)` را بنویسید که داخل `withTx` در `orders` و `order_items` درج کند، `23503` را به خطای دامنه‌ی 422 تبدیل کند، و با یک تست ثابت کنید insert ناموفق آیتم هیچ ردیف سفارشی باقی نمی‌گذارد.

## قدم بعدی

مقاله‌ی بعدی «NATS JetStream از Node.js» است.
