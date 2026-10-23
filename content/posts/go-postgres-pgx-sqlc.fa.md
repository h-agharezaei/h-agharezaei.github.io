+++
date = '2027-01-09T10:00:00+03:30'
draft = false
title = 'Postgres با pgx و sqlc در Go'
description = 'یک store واقعی PostgreSQL برای سرویس سفارش‌ها با pgx و sqlc: migration، connection pool، deadline روی query، SQL injection و همان تست سرویس.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "postgres", "pgx", "sqlc", "sql"]
cover = { image = "/images/covers/go-postgres-pgx-sqlc.fa.png", alt = "Postgres با pgx و sqlc در Go", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-http-api-stdlib/) API سفارش‌ها همه‌چیز را در یک map نگه می‌داشت. حالا یک دیتابیس واقعی به آن می‌دهیم. interface به نام `Repository` در سرویس تعریف شده است، همان‌طور که در [ساختار پروژه و Clean Architecture](/fa/posts/go-project-layout-clean-architecture/) دیدیم، پس store مربوط به Postgres فقط پیاده‌سازی دوم همان interface است. اول مستقیم با **pgx** (درایور و ابزارهای Postgres) کار می‌کنیم و بعد همان store را با **sqlc** تولید می‌کنیم.

> همه‌چیز با Go 1.26 روی macOS و روی یک PostgreSQL 18.3 واقعی اجرا شده است. Docker در دسترس نبود، برای همین دمو با ماژول `embedded-postgres` (نسخه‌ی v1.34.0) باینری‌های واقعی Postgres را روی یک پورت آزاد بالا می‌آورد. نسخه‌ی pgx برابر v5.11.0 و sqlc برابر v1.31.1 است.

## schema به شکل migration‌های SQL ساده

فایل migration منبع حقیقت schema است:

```sql
CREATE TABLE orders (
    id         text        PRIMARY KEY,
    customer   text        NOT NULL,
    cents      bigint      NOT NULL CHECK (cents > 0),
    status     text        NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'paid')),
    created_at timestamptz NOT NULL DEFAULT now()
);
```

یک runner کوچک فایل‌های `*.sql` را embed می‌کند، جدول `schema_migrations` را می‌سازد و هر فایل اجرانشده را به ترتیب و داخل یک transaction اعمال می‌کند. دوبار اجرا کردم و فایل فقط یک‌بار اعمال شد. ابزارهایی مثل goose یا golang-migrate این کار را بهتر انجام می‌دهند (down migration و قفل)؛ من runner را فقط برای مستقل ماندن دمو نوشتم.

## چرا pool و چطور تنظیمش کنیم

یک `pgx.Conn` هر لحظه فقط یک query را اجرا می‌کند. سرور هم‌زمان درخواست‌های زیادی می‌گیرد و باز کردن اتصال برای هر درخواست کند است و می‌تواند Postgres را از اتصال خالی کند. `pgxpool` تعداد محدودی اتصال نگه می‌دارد و قرض می‌دهد:

```go
cfg, err := pgxpool.ParseConfig(url)
cfg.MaxConns = 10
cfg.MinConns = 2
cfg.MaxConnLifetime = 30 * time.Minute
cfg.MaxConnIdleTime = 5 * time.Minute
cfg.ConnConfig.ConnectTimeout = 5 * time.Second
pool, err := pgxpool.NewWithConfig(ctx, cfg)
// then pool.Ping with a 3s timeout, so a bad URL fails at startup
```

`MaxConns` را بر اساس چیزی انتخاب کنید که دیتابیس در مجموع همه‌ی instance‌های شما تحمل می‌کند، نه تعداد هسته‌های CPU.

## Query، QueryRow، Exec و CollectRows

`Exec` برای دستوری است که ردیف برنمی‌گرداند، `QueryRow` برای یک ردیف و `Query` برای چند ردیف. `pgx.CollectRows` همراه با `pgx.RowToStructByName` ردیف‌ها را بر اساس نام ستون به struct تبدیل می‌کند. تگ‌های `db` روی struct مخصوص store است تا `domain.Order` از SQL پاک بماند:

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

store خطای `pgx.ErrNoRows` را به `domain.ErrNotFound` تبدیل می‌کند تا سرویس و handler هیچ‌وقت نفهمند زیرش چه دیتابیسی است (نگاشت خطا در [پیکربندی، لاگ و خطا](/fa/posts/go-config-logging-errors/) آمده است). `Save` یک `INSERT ... ON CONFLICT (id) DO UPDATE` است، یعنی همان رفتار بازنویسی map. اجرا روی سرور واقعی:

```
server_version: 18.3
applied 001_create_orders.sql
created {ID:4b3eb9b446634c1d Customer:ali Cents:1500 Status:new}
created {ID:67f26923bf79850f Customer:ali Cents:700 Status:new}
created {ID:21db0354404073a9 Customer:sara Cents:999 Status:new}
ali has 2 orders: [{ID:4b3eb9b446634c1d ...} {ID:67f26923bf79850f ...}]
get missing: order not found | is ErrNotFound: true
bad insert: ERROR: new row for relation "orders" violates check constraint "orders_cents_check" (SQLSTATE 23514)
```

خط آخر وقتی است که قانون domain را دور زدم و `CHECK` جلویم را گرفت: دیتابیس آخرین خط دفاع است.

## Deadline روی query

هر فراخوانی pgx یک `context` می‌گیرد. `pg_sleep(5)` را با deadline ۳۰۰ میلی‌ثانیه اجرا کردم:

```go
qctx, cancel := context.WithTimeout(ctx, 300*time.Millisecond)
defer cancel()
_, err := pool.Exec(qctx, `SELECT pg_sleep(5)`)
```

```
pg_sleep(5) with 300ms deadline: timeout: context deadline exceeded (after ~300ms) | is DeadlineExceeded: true
next query: 1 <nil>
```

`errors.Is(err, context.DeadlineExceeded)` کار می‌کند، فراخوانی سر deadline برگشت و نه بعد از پنج ثانیه، و pool query بعدی را عادی جواب داد. context درخواست را پایین بدهید تا اگر کلاینت قطع شد، query او هم لغو شود.

## SQL injection، واقعی

دو جست‌وجو روی یک جدول: یکی ورودی را به رشته می‌چسباند و یکی از `$1` استفاده می‌کند:

```go
q := "SELECT id FROM orders WHERE customer = '" + customer + "'" // do not do this
rows, err := pool.Query(ctx, `SELECT id FROM orders WHERE customer = $1`, customer)
```

```
input "sara"           concatenated: 1 rows <nil> | parameterized: 1 rows <nil>
input "x' OR '1'='1"   concatenated: 3 rows <nil> | parameterized: 0 rows <nil>
```

ورودی مخرب باعث شد query چسبانده‌شده هر سه سفارش را برگرداند؛ نسخه‌ی parameterized آن را اسم یک مشتری حساب کرد و چیزی پیدا نکرد. پارامترها جدا از متن SQL فرستاده می‌شوند، پس نمی‌توانند ساختار آن را عوض کنند. فقط مقدار می‌تواند پارامتر باشد: نام جدول و ستون نمی‌تواند، پس آن‌ها را با فهرست مجاز کنترل کنید.

## sqlc: بخش خسته‌کننده را تولید کنید

با sqlc شما SQL می‌نویسید و Go تایپ‌دار می‌گیرید. پیکربندی پوشه‌ی migration‌ها را به‌عنوان schema می‌خواند:

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

فایل `query.sql` سه query با annotation دارد (`GetOrder :one`، `ListOrdersByCustomer :many` و `UpsertOrder :exec`). دستور `go run github.com/sqlc-dev/sqlc/cmd/sqlc@v1.31.1 generate` را اجرا کردم و این امضاها تولید شد:

```go
func (q *Queries) GetOrder(ctx context.Context, id string) (Order, error)
func (q *Queries) ListOrdersByCustomer(ctx context.Context, customer string) ([]Order, error)
func (q *Queries) UpsertOrder(ctx context.Context, arg UpsertOrderParams) error
```

یک query اضافه کردم که ستونی به نام `total` را انتخاب می‌کرد و در schema نیست؛ `generate` با `query.sql:13:8: column "total" does not exist` شکست خورد، پس اشتباه‌ها قبل از اجرا معلوم می‌شوند. struct تولیدشده‌ی `Order` از `pgtype.Timestamptz` استفاده می‌کند و برای همین store من آن را دستی به `domain.Order` نگاشت می‌کند.

## یک تست، سه store

بررسی‌های سطح سرویس در یک helper هستند که هر `service.Repository` را می‌گیرد: ساخت و خواندن، رد شدن سفارش نامعتبر، و `ErrNotFound` برای سفارش ناموجود. store درون‌حافظه‌ای، store با pgx و store با sqlc همه همین را اجرا می‌کنند و هرکدام محافظ `var _ service.Repository = (*Store)(nil)` را دارند:

```
$ go test -v ./internal/store/postgres
--- PASS: TestService (0.00s)
    --- PASS: TestService/create_then_get (0.00s)
    --- PASS: TestService/invalid_order_is_rejected (0.00s)
    --- PASS: TestService/missing_order_is_ErrNotFound (0.00s)
PASS
```

پکیج sqlc هم همین زیرتست‌ها را گذراند. کد سرویس اصلاً تغییر نکرد.

## چند نکته که باید حواستان باشد

- `SELECT *` همراه `RowToStructByName` وقتی struct و ستون‌ها نخوانند خطا می‌دهد که مفید است، ولی در query‌های production ستون‌ها را صریح بنویسید.
- بعد از `WithTimeout` همیشه `defer cancel()` بگذارید و در لبه‌ی هر درخواست deadline تعیین کنید.
- pool را در `main` بسازید و هنگام خاموش‌شدن ببندید.
- خروجی sqlc کدی است که commit می‌کنید؛ آن را در CI دوباره تولید کنید و با diff شکست بدهید.
- Postgres توکار برای تست راحت است ولی بار اول باینری دانلود می‌کند؛ راه رایج دیگر، service container در CI است.

## قدم بعدی

در مقاله‌ی بعد: تراکنش‌ها و الگوی repository در Go، جایی که چند نوشتن باید با هم موفق یا با هم ناموفق شوند.
