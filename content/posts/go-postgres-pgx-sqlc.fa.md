+++
date = '2027-01-09T10:00:00+03:30'
draft = false
title = 'Postgres با pgx و sqlc در Go'
description = 'یک store واقعی PostgreSQL برای سرویس سفارش‌ها با pgx و sqlc: migration، connection pool، deadline روی query، SQL injection و همان تست سرویس.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "postgres", "pgx", "sqlc", "sql"]
cover = { image = "/images/covers/go-postgres-pgx-sqlc.fa.png", alt = "Postgres با pgx و sqlc در Go", hiddenInSingle = true }
+++

تا اینجا سرویس `orders` داده‌اش را در یک map نگه می‌دارد. پروسه را دوباره راه بیندازید و همه‌ی سفارش‌ها می‌روند. سرویس واقعی دیتابیس لازم دارد و در بک‌اندهای Go این خیلی وقت‌ها یعنی PostgreSQL. سؤال این است که این کار برای بقیه‌ی کد چه هزینه‌ای دارد. اگر چون ذخیره‌سازی عوض شده باید منطق سرویس را عوض کنید، چیزی در ساختار اشتباه است.

اینجا عوض نمی‌شود. یک تست سرویس هم با store درون‌حافظه‌ای، هم با storeای که با pgx نوشته‌ایم و هم با storeای که sqlc تولید کرده پاس می‌شود. دلیلش این است که `Repository` را خود سرویس تعریف کرده ([ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/))، پس Postgres فقط پیاده‌سازی دومِ interfaceی است که از قبل وجود داشت. سرویسِ این دمو همان سرویس آن نوشته است؛ handlerهای `net/http` [نوشته‌ی قبل](/fa/posts/go-http-api-stdlib/) هم روی همین interface سوارند. store مربوط به Postgres را در این دمو به آن سرور HTTP وصل نکرده‌ام؛ بررسی‌ها در سطح سرویس اجرا می‌شوند.

دو ابزار به کار می‌گیریم. **pgx** درایور و جعبه‌ابزار Postgres برای Go است: کتاب‌خانه‌ای که اتصال باز می‌کند، SQL می‌فرستد و نتیجه را می‌خواند. **sqlc** یک تولیدکننده‌ی کد است: شما SQL ساده می‌نویسید و آن برایش تابع‌های Go با نوع‌های امن تولید می‌کند. اول مستقیم با pgx کار می‌کنیم تا ببینیم چه می‌گذرد، بعد همان store را با sqlc تولید می‌کنیم.

> همه‌چیز دوباره با Go 1.27 روی macOS (arm64) و روی یک PostgreSQL 18.3 واقعی اجرا شده است. روی این ماشین Docker نیست، پس دمو باینری‌های واقعی Postgres را با ماژول `embedded-postgres` (نسخه‌ی v1.34.0) روی یک پورت آزادِ تصادفی و با پوشه‌ی داده‌ی موقت بالا می‌آورد که در پایان پاک می‌شود. pgx نسخه‌ی v5.11.0 است. شناسه‌ها در خروجی‌ها تصادفی‌اند و از اجرا به اجرا فرق می‌کنند.

## schema به‌شکل migration‌های SQL ساده

پیش از اینکه کد بتواند چیزی ذخیره کند، جدول باید وجود داشته باشد. {{< term "migration" "migration" >}} یک فایل SQL شماره‌دار است که schema را یک قدم جلو می‌برد و مجموعه‌ی فایل‌های migration تاریخچه‌ی schema شماست. اینجا فایل migration تنها منبع حقیقت است:

```sql
CREATE TABLE orders (
    id         text        PRIMARY KEY,
    customer   text        NOT NULL,
    cents      bigint      NOT NULL CHECK (cents > 0),
    status     text        NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'paid')),
    created_at timestamptz NOT NULL DEFAULT now()
);
```

به دو `CHECK` توجه کنید. آن‌ها قانون‌هایی را تکرار می‌کنند که domain از قبل اجرا می‌کند. این عمدی است: دیتابیس آخرین خط دفاع است و کمی بعد می‌بینیم که فعال می‌شود.

یک runner کوچک فایل‌های `*.sql` را در باینری embed می‌کند، جدولی به نام `schema_migrations` می‌سازد و هر فایلی را که هنوز آنجا ثبت نشده، به ترتیب و داخل یک تراکنش اجرا می‌کند. آن را دو بار پشت سر هم اجرا کردم و بار دوم کاری نکرد، برای همین خروجی فایل را یک‌بار اعمال‌شده نشان می‌دهد. ابزارهایی مثل goose یا golang-migrate این کار را بهتر می‌کنند (migration برگشتی، قفل بین نمونه‌ها). من runner را فقط برای مستقل‌بودن دمو خودم نوشتم.

## چرا pool و چطور تنظیمش کنیم

یک `pgx.Conn` در هر لحظه یک query را اجرا می‌کند. سرور چند درخواست را هم‌زمان پردازش می‌کند و باز کردن یک اتصال تازه برای هر درخواست کند است و می‌تواند Postgres را از پا دربیاورد، چون Postgres برای تعداد اتصال‌ها سقف دارد. {{< term "connection-pool" "connection pool" >}} (یعنی `pgxpool`) تعداد محدودی اتصال باز نگه می‌دارد و برای هر query یکی را قرض می‌دهد:

```go
cfg, err := pgxpool.ParseConfig(url)
cfg.MaxConns = 10
cfg.MinConns = 2
cfg.MaxConnLifetime = 30 * time.Minute
cfg.MaxConnIdleTime = 5 * time.Minute
cfg.HealthCheckPeriod = time.Minute
cfg.ConnConfig.ConnectTimeout = 5 * time.Second
pool, err := pgxpool.NewWithConfig(ctx, cfg)
// then pool.Ping with a 3s timeout, so a bad URL fails at startup
```

معنی هر تنظیم: `MaxConns` بیشترین تعداد اتصالی است که pool باز می‌کند و `MinConns` تعدادی که آماده نگه می‌دارد. `MaxConnLifetime` و `MaxConnIdleTime` اتصال‌های قدیمی یا بی‌استفاده را بازنشسته می‌کنند. `HealthCheckPeriod` هر چند وقت یک‌بار pool اتصال‌های بیکارش را وارسی می‌کند. `ConnectTimeout` مدت مجاز باز کردن یک اتصال را محدود می‌کند. `Ping` پایانی باعث می‌شود URL غلط یا دیتابیسِ خاموش همان موقع شروع برنامه شکست بخورد، نه در اولین درخواست.

`MaxConns` را از روی توان دیتابیس برای مجموع همه‌ی نمونه‌های سرویس انتخاب کنید، نه از روی تعداد CPU: ده نمونه با `MaxConns = 10` می‌توانند صد اتصال باز کنند.

## Query، QueryRow، Exec و CollectRows

در pgx، `Exec` برای دستوری است که ردیفی برنمی‌گرداند، `QueryRow` برای یک ردیف و `Query` برای چند ردیف. برای تبدیل ردیف‌ها به مقدار Go، `pgx.CollectRows` و `pgx.RowToStructByName` ستون‌ها را بر اساس نام به فیلدهای struct نگاشت می‌کنند. تگ‌های `db` روی همین struct هستند، پس `domain.Order` از SQL پاک می‌ماند:

```go
type row struct {
	ID        string    `db:"id"`
	Customer  string    `db:"customer"`
	Cents     int64     `db:"cents"`
	Status    string    `db:"status"`
	CreatedAt time.Time `db:"created_at"`
}

func (s *Store) Get(ctx context.Context, id string) (domain.Order, error) {
	rows, err := s.pool.Query(ctx, `SELECT * FROM orders WHERE id = $1`, id)
	if err != nil {
		return domain.Order{}, err
	}
	r, err := pgx.CollectOneRow(rows, pgx.RowToStructByName[row])
	if errors.Is(err, pgx.ErrNoRows) {
		return domain.Order{}, domain.ErrNotFound
	}
	if err != nil {
		return domain.Order{}, err
	}
	return r.order(), nil
}
```

`$1` جای‌نگهدار پارامتر اول است؛ در بخش injection دوباره می‌بینیمش. خط مهم همان است که `pgx.ErrNoRows` را مدیریت می‌کند: store آن را به `domain.ErrNotFound` ترجمه می‌کند، پس سرویس و handler هیچ‌وقت نمی‌فهمند زیرش کدام دیتابیس است (نگاشت به کدهای HTTP در [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) آمده). `Save` یک `INSERT ... ON CONFLICT (id) DO UPDATE` است که همان رفتار «بازنویسی» را می‌دهد که اختصاص به کلید map می‌داد.

برنامه‌ی دمو سه سفارش از راه سرویس می‌سازد، سفارش‌های یک مشتری را فهرست می‌کند، سفارشی ناموجود را می‌خواهد و در آخر یک ردیف بد را مستقیم و بدون domain درج می‌کند. چند خط درباره‌ی سرور هم چاپ می‌کند. این خروجی واقعی است:

```
server_version: 18.3
applied 001_create_orders.sql
pool max conns: 10
created {ID:11e486ac452931b4 Customer:ali Cents:1500 Status:new}
created {ID:49b2cbb9c8bd1ea1 Customer:ali Cents:700 Status:new}
created {ID:6d623fe5f1ed1ada Customer:sara Cents:999 Status:new}
ali has 2 orders: [{ID:11e486ac452931b4 Customer:ali Cents:1500 Status:new} {ID:49b2cbb9c8bd1ea1 Customer:ali Cents:700 Status:new}]
get missing: order not found | is ErrNotFound: true
bad insert: ERROR: new row for relation "orders" violates check constraint "orders_cents_check" (SQLSTATE 23514)
```

خط‌به‌خط: دو خط اول می‌گویند کدام نسخه‌ی Postgres جواب داد و migration اجرا شد. pool سقف ۱۰ را گزارش می‌دهد. سه خط `created` سفارش‌ها هستند، با شناسه‌های تصادفی که در Go ساخته شده‌اند. خط بعد فقط دو سفارش `ali` را فهرست می‌کند. بعد یک شناسه‌ی ناموجود `order not found` برمی‌گرداند و `errors.Is` تأیید می‌کند خطای `ErrNotFound` خودمان است، نه خطای pgx. خط آخر همان {{< term "check-constraint" "قید CHECK" >}} است که وقتی `cents = -5` را مستقیم در جدول درج کردم فعال شد: دیتابیس آن را رد کرد و یک کد {{< term "sqlstate" "SQLSTATE" >}} به نام `23514` گزارش داد. قانون domain برای این درج اصلاً اجرا نشد، و نکته همین است: حتی اگر مسیری از کد قانون را فراموش کند، داده معتبر می‌ماند.

## deadline روی queryها

یک query می‌تواند کند باشد: قفل، ایندکس گم‌شده، سرور شلوغ. هر فراخوانی pgx یک {{< term "context" "context" >}} می‌گیرد، پس می‌توانید برایش deadline بگذارید. برای دیدن کارش، `pg_sleep(5)` را اجرا کردم، یعنی queryای که پنج ثانیه هیچ کاری نمی‌کند، با deadline برابر ۳۰۰ میلی‌ثانیه:

```go
qctx, cancel := context.WithTimeout(ctx, 300*time.Millisecond)
defer cancel()
_, err := pool.Exec(qctx, `SELECT pg_sleep(5)`)
```

```
pg_sleep(5) with 300ms deadline: timeout: context deadline exceeded (after ~300ms) | is DeadlineExceeded: true
next query: 1 <nil>
```

خط اول نشان می‌دهد فراخوانی بعد از حدود ۳۰۰ میلی‌ثانیه برگشت، نه پنج ثانیه، و `errors.Is(err, context.DeadlineExceeded)` روی خطا کار می‌کند. خط دوم نشان می‌دهد pool سالم مانده: query بعدی، `SELECT 1`، بدون خطا `1` برگرداند. در سرور، context درخواست را تا همین فراخوانی‌ها پایین بدهید تا اگر مشتری قطع شد، queryاش هم لغو شود.

## SQL injection، واقعی

چرا مثال‌های بالا `$1` به کار بردند و رشته را نساختند؟ دو جست‌وجو روی همین جدول داریم: یکی ورودی را به متن SQL می‌چسباند و دیگری از جای‌نگهدار استفاده می‌کند. دمو هر دو را یک‌بار با نام معمولی و یک‌بار با ورودی بدخواهانه اجرا می‌کند:

```go
q := "SELECT id FROM orders WHERE customer = '" + customer + "'" // do not do this
rows, err := pool.Query(ctx, `SELECT id FROM orders WHERE customer = $1`, customer)
```

```
input "sara"           concatenated: 1 rows <nil> | parameterized: 1 rows <nil>
input "x' OR '1'='1"   concatenated: 3 rows <nil> | parameterized: 0 rows <nil>
```

برای `sara` هر دو یک سفارش پیدا می‌کنند. برای ورودی بدخواهانه، queryی که ورودی را چسبانده شبیه `... WHERE customer = 'x' OR '1'='1'` شد، شرطی که همیشه درست است، پس هر سه سفارش جدول را برگرداند. این همان {{< term "sql-injection" "SQL injection" >}} است. queryی که {{< term "parameterized-query" "پارامتری" >}} بود همان متن را به‌عنوان نام مشتری گرفت، کسی با آن نام پیدا نکرد و صفر ردیف برگرداند. پارامترها جدا از متن SQL می‌روند، پس هیچ‌وقت نمی‌توانند ساختار آن را عوض کنند. یک محدودیت: فقط مقدارها می‌توانند پارامتر باشند. اسم جدول و ستون نمی‌تواند، پس اگر یک‌وقت اسم پویا لازم شد، آن را با فهرستی ثابت مقایسه کنید.

## sqlc: بخش خسته‌کننده را تولید کنید

نوشتن struct‌های `row` و کد scan با دست تکراری است. با sqlc شما SQL می‌نویسید و Go با نوع‌های امن می‌گیرید. کانفیگش پوشه‌ی migrationها را به‌عنوان schema می‌خواند، پس تعریف جدول فقط یکی است:

```yaml
version: "2"
sql:
  - engine: "postgresql"
    schema: "migrations"
    queries: "query.sql"
    gen:
      go:
        package: "db"
        out: "internal/store/sqlcstore/db"
        sql_package: "pgx/v5"
```

فایل `query.sql` سه query دارد که هرکدام در یک کامنت نام و نوع دارد: `GetOrder :one`، `ListOrdersByCustomer :many` و `UpsertOrder :exec`. اجرای `sqlc generate` این امضاها را تولید کرد:

```go
func (q *Queries) GetOrder(ctx context.Context, id string) (Order, error)
func (q *Queries) ListOrdersByCustomer(ctx context.Context, customer string) ([]Order, error)
func (q *Queries) UpsertOrder(ctx context.Context, arg UpsertOrderParams) error
```

این امضاها از فایل تولیدشده‌ی دمو کپی شده‌اند (سرآیند آن می‌گوید با sqlc v1.31.1 ساخته شده). این بار نتوانستم sqlc را دوباره دانلود کنم، چون mirror ماژول‌ها timeout داد، پس `generate` را دوباره اجرا نکردم. آنچه بررسی کردم این است که کد تولیدشده‌ی commit‌شده با این امضاها می‌خواند و کل store مبتنی بر sqlc تست‌های پایین را پاس می‌کند. خودِ اجرای `generate` و آزمایش پاراگراف بعد از اجرای اولیه‌ی من هستند.

یک ویژگی مفید: sqlc موقع تولید، SQL شما را با schema مقایسه می‌کند. در اجرای اولیه queryای اضافه کردم که ستونی به نام `total` را انتخاب می‌کرد که در جدول نیست، و `generate` با `query.sql:13:8: column "total" does not exist` شکست خورد. پس غلط تایپی در query پیش از اجرا گرفته می‌شود، نه در production. نوع تولیدشده‌ی `Order` برای `created_at` از `pgtype.Timestamptz` استفاده می‌کند، برای همین store من آن را در چند خط با دست به `domain.Order` نگاشت می‌کند.

## یک تست، سه store

از کجا بدانیم این سه store رفتار یکسان دارند؟ بررسی‌های سطح سرویس در یک تابع کمکی هستند که هر `service.Repository` را می‌گیرد: ساختن و بعد خواندن، رد شدن سفارش نامعتبر، و `ErrNotFound` بودن سفارش ناموجود. store درون‌حافظه‌ای، store با pgx و store با sqlc هر سه آن را اجرا می‌کنند و هرکدام محافظ زمان کامپایل `var _ service.Repository = (*Store)(nil)` را از نوشته‌ی ساختار پروژه دارد:

```
$ go test -v ./internal/store/postgres
--- PASS: TestService (0.00s)
    --- PASS: TestService/create_then_get (0.00s)
    --- PASS: TestService/invalid_order_is_rejected (0.00s)
    --- PASS: TestService/missing_order_is_ErrNotFound (0.00s)
PASS
```

(خط‌های `=== RUN` را حذف کرده‌ام.) تست Postgres در `TestMain` یک سرور واقعی بالا می‌آورد، migration را اجرا می‌کند، سه زیرتست را می‌گذراند و سرور را متوقف می‌کند. پکیج‌های memory و sqlc هم همین سه زیرتست را پاس کردند. کد سرویس اصلاً عوض نشد. این نسخه‌ی کوچکی از دلیل لایه‌بندی است.

## دام‌های pgx و sqlc

- `SELECT *` همراه `RowToStructByName` وقتی struct و ستون‌ها فرق دارند شکست می‌خورد. این به‌عنوان زنگ هشدار مفید است، ولی در queryهای production ستون‌ها را صریح فهرست کنید تا اضافه‌شدن ستون در آینده کد را نشکند.
- بعد از `WithTimeout` همیشه `defer cancel()` بگذارید و در لبه‌ی هر درخواست deadline تعیین کنید.
- pool را در `main` نگه دارید، یک‌بار بسازید و هنگام shutdown ببندید.
- خروجی sqlc کدی است که commit می‌کنید. آن را در CI دوباره تولید کنید و اگر diff داشت build را شکست بدهید، تا کد تولیدشده هیچ‌وقت از SQL جدا نیفتد.
- Postgres توکار برای تست راحت است، ولی طبق مستنداتش باینری‌های Postgres را در اولین استفاده دانلود می‌کند. سرویس کانتینری Postgres در CI گزینه‌ی رایج دیگر است.

## قدم بعدی

قدم بعدی «تراکنش و الگوی Repository در Go» است. اینجا هر نوشتن خودش commit می‌شود، در حالی که کار واقعی اغلب چند نوشتن لازم دارد که باید با هم موفق شوند یا با هم شکست بخورند.
