+++
date = '2027-02-11T10:00:00+03:30'
draft = false
title = 'Postgres از Node.js با pg'
description = 'Postgres از Node.js با pg: Pool، پارامتر، غافلگیری نوع‌ها، تراکنش، SQL injection، خطاهای SQLSTATE، timeout و خاموشی تمیز، همه با اجرای واقعی.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "postgres", "pg", "sql", "connection-pool"]
cover = { image = "/images/covers/node-postgres-pg.fa.png", alt = "Postgres از Node.js با pg", hiddenInSingle = true }
+++

باگی هست که به‌راحتی از چشم می‌افتد. `SELECT count(*) AS n FROM orders` را اجرا می‌کنید و برای «یکی بیشتر از تعداد» می‌نویسید `row.n + 1`. با ۳۰ سفارش انتظار دارید ۳۱ بگیرید، ولی `301` می‌گیرید. نه چیزی کرش می‌کند و نه هشداری می‌آید. عدد فقط غلط است.

علتش این است که `pg`، درایور Postgres برای Node.js، مقدار `count(*)` را به‌شکل رشته برمی‌گرداند و `+` به‌جای جمع، کاراکترها را به هم می‌چسباند. این فقط اولین غافلگیری از چند غافلگیری است که بین برنامه‌ی Node.js و دیتابیس منتظرتان است. بقیه‌اش اتصال‌هایی است که باید با احتیاط بینشان تقسیم کرد، تراکنش‌هایی که باید روی یک اتصال بمانند، و یک اشتباه خیلی قدیمی: ساختن SQL از ورودی کاربر.

در این مقاله `pg` (همان node-postgres) را به یک PostgreSQL واقعی وصل می‌کنم و این‌ها را یکی‌یکی می‌بینیم، هرکدام با یک اسکریپت کوچک و خروجی واقعی‌اش. آدرس دیتابیس از یک متغیر محیطی به اسم `DATABASE_URL` می‌آید؛ همان نوع تنظیمی که در [ساختار پروژه و کانفیگ در Node.js](/fa/posts/node-project-structure-config/) یاد گرفتیم یک‌بار بخوانیم و اعتبارسنجی کنیم. برای مقایسه، همین موضوع‌ها در Go در [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/) و برای تراکنش در [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/) آمده است.

> همه‌چیز را با Node نسخه‌ی v20.13.1، `pg` نسخه‌ی 8.23.1 و `pg-cursor` نسخه‌ی 2.22.1 (از lockfile دمو) روی PostgreSQL 18.3 در loopback اجرا کردم. دیتابیس از schema مشترک «shop» سری Databases (مشتری، محصول، سفارش و آیتم سفارش) استفاده می‌کند و `setup.sql` چند ردیف به آن اضافه می‌کند: ۶ مشتری، ۲ محصول و ۳۰ سفارش. روی این ماشین Docker نیست، پس Postgres از باینری‌های embedded و روی یک پورت آزاد تصادفی بالا آمد. اسکریپت‌ها مثال محلی‌اند. زمان‌بندی نشان نمی‌دهم.

## یک استخر اتصال و اولین query

برای حرف زدن با Postgres باید یک اتصال باز کنید: یک اتصال TCP به سرور به‌اضافه‌ی ورود با نام کاربری. این کار نسبت به یک query معمولی کند است و سرور برای هر اتصال منابعی نگه می‌دارد. (طبق مستندات Postgres، سقف پیش‌فرض ۱۰۰ اتصال است.) برای همین یک سرویس وب به‌ازای هر درخواست اتصال تازه باز نمی‌کند. چند اتصال را باز نگه می‌دارد و بین درخواست‌ها قرض می‌دهد.

{{< term "connection-pool" "connection pool (استخر اتصال)" >}} دقیقاً همین است. `pool.query(...)` یک اتصال بیکار را قرض می‌گیرد، SQL را رویش اجرا می‌کند و پس می‌دهد. اگر همه‌ی اتصال‌ها مشغول باشند، فراخوانی منتظر می‌ماند تا یکی آزاد شود.

مقدارهای query به‌شکل *پارامتر* می‌روند: در متن SQL `$1` و `$2` می‌نویسیم و مقدارهای واقعی را در یک آرایه کنارش می‌دهیم. هرگز مقدارها را داخل رشته‌ی SQL نچسبانید. دلیلش را در بخش injection می‌بینیم؛ فعلاً فقط به شکل کار نگاه کنید:

```js
const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 4 });
const r = await pool.query('SELECT id, name FROM customers WHERE country = $1 ORDER BY id LIMIT $2', ['DE', 2]);
console.log(r.rows, r.rowCount, r.fields.map(f => f.name), r.command);
```

`max: 4` استخر را به چهار اتصال محدود می‌کند. نتیجه شامل ردیف‌ها، تعداد ردیف، نام ستون‌ها و نوع دستور است. این را چاپ کرد:

```text
[ { id: '1', name: 'c1' }, { id: '2', name: 'c2' } ] 2 [ 'id', 'name' ] SELECT
```

هر ردیف یک شیء ساده است. به `id` نگاه کنید: رشته‌ی `'1'` است، نه عدد 1. همان غافلگیری `count(*)` است و یک بخش جدا می‌خواهد.

## چرا عددها رشته برمی‌گردند

نوع `bigint` در Postgres تا ۶۴ بیت جا دارد. عدد در JavaScript یک double است که فقط تا 2^53 عدد صحیح را دقیق نگه می‌دارد. اگر `pg` هر `bigint` را به عدد تبدیل می‌کرد، مقدارهای بزرگ بی‌صدا خراب می‌شدند؛ پس به‌طور پیش‌فرض رشته می‌دهد. همین برای `numeric` هم هست (اعشار دقیق، که double نمی‌تواند دقیق نگه دارد)، و `count(*)` و `sum` هم `bigint` یا `numeric` تولید می‌کنند.

یک اسکریپت چند نوع را در یک query می‌خواهد و نوع JavaScript هر ستون را چاپ می‌کند:

```text
n       string  30
s       string  46500
big     string  1
num     string  12.50
i       number  7
ts      object  Date  <the current time>
```

(ستون‌ها به‌ترتیب `count(*)`، `sum(total_cents)`، `1::bigint`، `12.50::numeric`، `7::int` و `now()` هستند. زمان واقعی خط آخر را با یک جای‌نگهدار عوض کردم؛ زمان اجرا بود.) فقط `int` ساده عدد می‌شود. `timestamptz` به `Date` در JavaScript تبدیل می‌شود.

خرابی تا کجا می‌تواند برود؟ `9007199254740993::bigint` را خواستم، یکی بیشتر از 2^53. رشته درست رسید و تبدیلش به عدد رقم آخر را از دست داد:

```text
31 301
9007199254740993 9007199254740992
```

خط اول `Number(row.n) + 1` و `row.n + 1` است: همان 301 اول مقاله. خط دوم مقدار بزرگ است، یک‌بار به‌شکل رشته و یک‌بار بعد از `Number()`.

پس تبدیل را عمدی انجام دهید. وقتی می‌دانید مقدار کوچک است `Number(row.n)`، وقتی ممکن است بزرگ باشد `BigInt` یا خود رشته، یا در SQL با cast، مثلاً `count(*)::int`. ستون {{< term "jsonb" "jsonb" >}} در عوض خودش به یک شیء واقعی parse می‌شود (`meta.tags` برابر `['a', 'b']` بود؛ [JSONB و جست‌وجوی متنی](/fa/posts/db-jsonb-fulltext-search/) را ببینید). در همان اسکریپت یک قیمت `numeric(10,2)` به‌شکل رشته‌ی `'12.50'` آمد که اعشارش را دقیق نگه می‌دارد. pgx در Go مقدار `bigint` را مستقیم در `int64` می‌ریزد؛ در Node پیش‌فرض امن رشته است.

## وقتی استخر تمام می‌شود

استخر سقف دارد؛ پس سؤال طبیعی این است که وقتی همه قرض گرفته‌اند چه می‌شود. در این اسکریپت `max: 2` و `connectionTimeoutMillis: 300` گذاشتم، هر دو اتصال را با `pool.connect()` گرفتم و پس ندادم، و بعد query سوم را زدم:

```text
total/idle/waiting 2 0 0
Error | timeout exceeded when trying to connect | undefined
after release 2 2
after idle timeout 0 0
```

خط‌به‌خط: وقتی دو اتصال قرض گرفته شده، استخر ۲ اتصال دارد، ۰ بیکار و ۰ منتظر (query سوم هنوز شروع نشده). query سوم منتظر می‌ماند و بعد از ۳۰۰ میلی‌ثانیه خطای «timeout exceeded when trying to connect» می‌دهد (این خطا `code` ندارد، برای همین `undefined` چاپ شده). بعد از اینکه هر دو را پس دادم دوباره بیکار شدند (۲ کل، ۲ بیکار). با `idleTimeoutMillis: 1000` اتصال بیکار بعد از یک ثانیه بسته می‌شود و خط آخر ۰ را نشان می‌دهد.

نکته‌ی مهم این است که استخر تمام‌شده فوری خطا نمی‌دهد. query منتظر می‌ماند. طبق مستندات pg مقدار پیش‌فرض `connectionTimeoutMillis` صفر است، یعنی تا ابد صبر کن. پس درخواست گیر می‌کند تا کسی یک اتصال پس بدهد. اتصالی که قرض گرفته شده و هرگز `release` نشده، یعنی نشتی، دقیقاً همین شکل را دارد. timeout بگذارید تا به‌جای گیرکردن، خطا بگیرید.

## تراکنش یک اتصال می‌خواهد

گاهی چند دستور باید با هم موفق یا با هم شکست بخورند، مثلاً ساختن یک سفارش و آیتم‌هایش. {{< term "transaction" "تراکنش" >}} همین کار را می‌کند: `BEGIN` می‌فرستید، دستورها را اجرا می‌کنید و بعد با `COMMIT` همه را نگه می‌دارید یا با `ROLLBACK` همه را برمی‌گردانید.

تراکنش روی یک اتصال زندگی می‌کند. اگر `BEGIN` و `COMMIT` را با `pool.query` بفرستید، هر فراخوانی ممکن است اتصال دیگری بگیرد و تراکنش بی‌معنی می‌شود. پس با `pool.connect()` یک اتصال از استخر بیرون می‌آورید، همه‌چیز را روی آن اجرا می‌کنید و در `finally`، هر اتفاقی بیفتد، پسش می‌دهید:

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

برای امتحانش، اسکریپت اول دو سفارش `paid` را commit می‌کند. بعد تراکنشی اجرا می‌کند که یک insert معتبر دارد و بعد یک insert برای مشتریِ ناموجود، که باید شکست بخورد:

```text
paid before 0
after commit 2
inside tx sees 3
failed: 23503 orders_customer_id_fkey
after rollback 2 idle 1 total 1
```

اول هیچ سفارش paid نداریم و بعد از تراکنش اول ۲ تا داریم. در تراکنش ناموفق، اتصال ردیف commitنشده‌ی خودش را می‌بیند (۳). insert دوم کلید خارجی `orders_customer_id_fkey` را نقض می‌کند، پس کد rollback می‌کند و شمار به ۲ برمی‌گردد. خط آخر نشان می‌دهد اتصال به استخر برگشته (۱ بیکار از ۱ کل).

## SQL injection

حالا اشتباه قدیمی. فرض کنید query را با چسباندن کشور به متن بسازید. اسکریپت یک جست‌وجو را به هر دو شکل اجرا می‌کند. ورودی «بد» این است: `x' OR '1'='1`. رشته را زودتر می‌بندد و شرطی اضافه می‌کند که همیشه درست است.

```text
concat normal: 1 rows
concat evil  : 6 rows
param  evil  : 0 rows
notes before: notes
after param attack : notes
after concat attack: null
```

ورودی معمولی تنها مشتری UK را پیدا می‌کند. با چسباندن رشته، ورودی بد هر ۶ مشتری را برگرداند. با `$1`، همان متن فقط نام کشوری است که وجود ندارد، پس صفر ردیف. این {{< term "sql-injection" "SQL injection" >}} است: ورودی کاربر بخشی از خود SQL شد.

بدتر از افشای ردیف‌ها هم می‌شود. ورودی `x'; DROP TABLE notes; --` دستور را تمام می‌کند و دستور دیگری شروع می‌کند. بعد از فراخوانی با پارامتر، جدول `notes` هنوز بود. بعد از فراخوانی با رشته‌ی چسبانده‌شده واقعاً رفته بود (`to_regclass` مقدار `null` داد، یعنی چنین جدولی نیست). البته جدول دموی خودم بود.

دلیل امن‌بودن پارامترها این است که جدا از متن SQL فرستاده می‌شوند (این همان {{< term "parameterized-query" "parameterized query" >}} است). دیتابیس اول دستور را parse می‌کند و بعد مقدارها را جا می‌دهد، پس مقدار هرگز ساختار query را عوض نمی‌کند. یک محدودیت: نام جدول و ستون نمی‌تواند پارامتر باشد. اگر نامی از کاربر می‌آید، آن را با یک فهرست مجاز ثابت مقایسه کنید.

## خواندن خطا با SQLSTATE

وقتی query شکست می‌خورد، `pg` خطایی با ویژگی `code` پرتاب می‌کند. آن {{< term "sqlstate" "SQLSTATE" >}} است، یک کد استاندارد پنج‌کاراکتری، و `err.constraint` نام قیدی را می‌دهد که نقض شده. به `code` شاخه بزنید، نه به متن پیام، چون پیام‌ها برای آدم‌ها هستند و ممکن است عوض شوند. یک تابع می‌تواند کدهای مهم برای شما را به خطای دامنه‌ی خودتان تبدیل کند، به سبک [خطا و unhandled rejection در Node.js](/fa/posts/node-errors-unhandled-rejections/):

```js
function mapPgError(err) {
  switch (err.code) {
    case '23505': return new DomainError('conflict', 'already exists');
    case '23503': return new DomainError('invalid', 'referenced row does not exist');
    case '23514': return new DomainError('invalid', 'value violates a rule');
    case '57014': return new DomainError('timeout', 'query took too long');
    default: return err;
  }
}
```

`23505` نقض unique، `23503` نقض کلید خارجی، `23514` نقض check و `57014` لغوشدن دستور است. اسکریپت چهار شکست ایجاد می‌کند و هرکدام را نگاشت می‌کند (خط‌های `->` وضعیتی به سبک HTTP است که دمو انتخاب کرده):

```text
dup email | code 23505 | constraint customers_email_key | detail Key (email)=(ada@example.com) already exists.
   -> 409 conflict: already exists
bad fk   | code 23503 | constraint orders_customer_id_fkey | detail Key (customer_id)=(999999) is not present in table "customers".
   -> 422 invalid: referenced row does not exist
check    | code 23514 | constraint orders_status_check | detail Failing row contains (36, 1, weird, 2026-11-04 18:25:47.506092+03:30, 0).
   -> 422 invalid: value violates a rule
syntax   | code 42601 | constraint undefined | detail undefined
   -> unmapped, rethrow: syntax error at or near "SELEC"
```

ایمیل تکراری، مشتریِ ناموجود و وضعیت نامعتبر هرکدام به جواب روشنی نگاشت شدند. غلط تایپی `SELEC` کد `42601` دارد و قیدی ندارد؛ کسی آن را نگاشت نکرده و کد دوباره پرتابش می‌کند: خطای غیرمنتظره باید خطا بماند. (شناسه‌ی ردیف و زمان در خط `check` در هر اجرا فرق می‌کند.)

## timeout، و خطایی که process را می‌اندازد

query کند به سقف نیاز دارد و `pg` دو سقف دارد که یکی نیستند. با `statement_timeout: 200` خودِ *سرور* هر دستوری را که بیشتر از ۲۰۰ میلی‌ثانیه طول بکشد لغو می‌کند و اتصال قابل استفاده می‌ماند. با `query_timeout: 200` خودِ *client* از انتظار دست می‌کشد و خطا پرتاب می‌کند، ولی به سرور خبر داده نمی‌شود:

```text
statement_timeout: 57014 canceling statement due to statement timeout
pool still works: 1
query_timeout: undefined Query read timeout
after: 1
```

حالت اول SQLSTATE دارد (57014) و استخر بعدش کار می‌کند. حالت دوم `code` ندارد و فقط پیام «Query read timeout» را دارد. آیا سرور هنوز مشغول است؟ با یک اسکریپت یک‌بارمصرف بررسی کردم: بعد از اینکه client از `pg_sleep(2)` دست کشید، یک اتصال دوم در `pg_stat_activity` نگاه کرد و آن دستور را هنوز `active` با `wait_event` برابر `PgSleep` دید؛ بعد از تمام‌شدن sleep از بین رفت. پس `statement_timeout` را ترجیح دهید که کار را واقعاً متوقف می‌کند.

خطر دوم این است که یک اتصال بیکار وقتی کسی از آن استفاده نمی‌کند بمیرد. من با `pg_terminate_backend` از یک اتصال دیگر آن را کشتم. استخر رویداد `error` اتصال را دوباره منتشر می‌کند و در Node رویداد `error` بدون شنونده پرتاب می‌شود. بدون handler، process کرش کرد:

```text
node:events:497
      throw er; // Unhandled 'error' event
      ^

error: terminating connection due to administrator command
...
  severity: 'FATAL',
  code: '57P01',
```

(stack trace را بریدم؛ مسیرهایش از پوشه‌ی موقت من بود.) با یک خط، `pool.on('error', (err, client) => ...)`، process زنده ماند و استخر اتصال مرده را کنار گذاشت:

```text
pool error event: 57P01 terminating connection due to administrator command
survived; idle clients: 0
```

هر استخری در یک سرویس بلندمدت باید این handler را داشته باشد.

## نتیجه‌ی بزرگ و خاموشی تمیز

اگر query تعداد زیادی ردیف برگرداند، بارکردن همه‌ی آن‌ها یک‌جا در حافظه ایده‌ی بدی است. بسته‌ی `pg-cursor` ردیف‌ها را دسته‌دسته می‌خواند. اسکریپت یک سری ۲۵ ردیفی را با اندازه‌ی دسته‌ی ۱۰ می‌خواند و دسته‌های ۱۰، ۱۰ و ۵ می‌گیرد (`total 25`). cursor باید روی یک اتصال اختصاصی (`pool.connect()`) باشد، نه با `pool.query`.

برای خاموشی، `pool.end()` قبل از بستن منتظر می‌ماند اتصال‌های قرض‌گرفته‌شده برگردند. برای دیدنش یک سرور HTTP راه انداختم که handler آن `pg_sleep(1)` اجرا می‌کند و 42 برمی‌گرداند، یک درخواست فرستادم و وقتی query هنوز در حال اجرا بود `SIGTERM` فرستادم. پاسخ `42` باز هم رسید و لاگ این بود: `SIGTERM: closing server, then pool`، `pool ended, exiting` و کد خروج ۰. ترتیب مهم است: اول پذیرفتن درخواست جدید را متوقف کنید، بعد استخر را ببندید. همان الگوی [سرور HTTP با node:http](/fa/posts/node-http-server/) است.

## جاهایی که داده‌ی pg خراب می‌شود

- **چسباندن مقدار به SQL.** همیشه پارامتر بدهید. نام جدول یا ستون از کاربر فهرست مجاز می‌خواهد، چون نام‌ها پارامتر نمی‌شوند.
- **اعتماد به نوع عدد.** `bigint`، `numeric`، `count(*)` و `sum` رشته‌اند. تبدیل را عمدی انجام دهید یا در SQL cast کنید، وگرنه `+` رشته‌ها را به هم می‌چسباند.
- **تراکنش با `pool.query`.** از `pool.connect()` استفاده کنید و `release()` را در `finally` بگذارید. clientای که هرگز آزاد نشود، آهسته استخر را خالی می‌کند.
- **بدون سقف و بدون تور ایمنی.** `connectionTimeoutMillis` و `statement_timeout` بگذارید و handler `pool.on('error')` اضافه کنید، وگرنه یک اتصال بیکارِ مرده می‌تواند process را بیندازد.
- **خواندن متن خطا.** به `err.code` (و `err.constraint`) شاخه بزنید، نه به متن.

## تمرین

تابع `createOrder(customerId, productId, qty)` را بنویسید که در `withTx` در `orders` و `order_items` درج می‌کند. `23503` را به خطای دامنه‌ی ۴۲۲ نگاشت کنید و با یک تست ثابت کنید که درج ناموفق آیتم هیچ ردیفی در `orders` باقی نمی‌گذارد.

## قدم بعدی

مقاله‌ی بعد «NATS JetStream از Node.js» است. بعد از دیتابیس نوبت ستون دوم یک backend است، پیام‌رسانی: چطور پیامی بفرستیم که گم نشود.
