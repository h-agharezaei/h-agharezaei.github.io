+++
date = '2027-01-19T10:00:00+03:30'
draft = false
title = 'تراکنش و الگوی Repository در Go'
description = 'تراکنش‌ها با pgx در Go: rollback، تابع کمکی WithTx، unit of work روی repository، lost update، SELECT FOR UPDATE، retry برای serializable و مشکل N+1.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "postgres", "transactions", "pgx", "repository"]
cover = { image = "/images/covers/go-transactions-patterns.fa.png", alt = "تراکنش و الگوی Repository در Go", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-postgres-pgx-sqlc/) سرویس سفارش‌ها یک store واقعی Postgres گرفت، ولی هر فراخوانی دنیای جدا از بقیه بود. کار واقعی اغلب دو نوشتن می‌خواهد که یا هر دو انجام شوند یا هیچ‌کدام. این مقاله درباره‌ی **تراکنش** (transaction) در pgx است، اینکه چطور آن را از کد domain دور نگه داریم، و اینکه کدام مشکل‌های هم‌زمانی را حل می‌کند و کدام را نه.

> Go 1.26، pgx v5.11.0 و یک PostgreSQL 18.3 واقعی که ماژول embedded-postgres بالا می‌آورد، مثل قبل. دمو یک کپی محلی از دموی قبلی است با migration دوم که جدول `accounts` (موجودی باید بین 0 و 10000 باشد، با دو `CHECK` نام‌دار) و جدول `order_items` را اضافه می‌کند.

## چرا تراکنش

انتقال پول دو `UPDATE` است: کم کردن از alice و اضافه کردن به carol. موجودی carol برابر 9950 و سقفش 10000 است، پس اضافه کردن 100 باید شکست بخورد. وقتی مستقیم از pool استفاده می‌کنیم، هر دستور جداگانه commit می‌شود:

```
before: alice=1000 carol=9950 total=10950
transfer error: account limit exceeded
after : alice=900 carol=9950 total=10850
```

برداشت commit شد، واریز شکست خورد و 100 واحد غیب شد. حالا همان انتقال داخل یک تراکنش:

```
transfer error: account limit exceeded | is ErrLimit: true
after : alice=1000 carol=9950 total=10950
```

هیچ چیز تغییر نکرد. این همان **atomicity** است: یا همه، یا هیچ.

## Begin، Commit، Rollback

```go
tx, err := pool.Begin(ctx)
if err != nil {
	return err
}
defer tx.Rollback(ctx) // safe to leave in place
// ... tx.Exec, tx.Query ...
return tx.Commit(ctx)
```

`defer` تضمین می‌کند هر `return` زودهنگام rollback کند. بعد از commit موفق، فراخوانی deferred ضرری ندارد؛ برای دیدنش خودم صدایش زدم:

```
commit: <nil>
rollback after commit: tx is closed | is ErrTxClosed: true
```

پس آن خطا را نادیده بگیرید. تراکنش تا پایانش یک اتصال از pool را نگه می‌دارد؛ کوتاهش کنید و داخلش هرگز درخواست HTTP نزنید.

## تابع کمکی WithTx

تکرار این بلوک در همه‌جا خطا می‌آورد، پس یک‌بار بسته‌بندی‌اش می‌کنیم:

```go
func WithTx(ctx context.Context, pool *pgxpool.Pool, opts pgx.TxOptions, fn func(pgx.Tx) error) error {
	tx, err := pool.BeginTx(ctx, opts)
	if err != nil {
		return err
	}
	defer func() {
		if p := recover(); p != nil {
			_ = tx.Rollback(ctx)
			panic(p)
		}
	}()
	if err := fn(tx); err != nil {
		_ = tx.Rollback(ctx)
		return err
	}
	return tx.Commit(ctx)
}
```

خطا یعنی rollback، panic یعنی rollback و دوباره panic، در غیر این صورت commit. در `fn` موجودی alice را صفر کردم و بعد panic زدم؛ بعد از `recovered: boom` موجودی هنوز 1000 بود. pgx هم تابع `pgx.BeginFunc` را با همین ایده دارد.

## یک repository، چه روی pool چه روی تراکنش

repository نباید بداند داخل تراکنش اجرا می‌شود یا نه. `*pgxpool.Pool` و `pgx.Tx` این سه متد را مشترک دارند، پس repository به یک interface کوچک وابسته می‌شود که معمولاً **DBTX** می‌نامندش:

```go
type DBTX interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

type Repo struct{ db DBTX }
func NewRepo(db DBTX) Repo { return Repo{db: db} }
```

سرویس باید مرز تراکنش را تعیین کند، بدون اینکه pgx را import کند. برای این کار یک interface به نام **unit of work** دارد و پکیج Postgres پیاده‌سازی‌اش می‌کند:

```go
// package bank (no pgx import)
type UnitOfWork interface {
	Do(ctx context.Context, fn func(Accounts) error) error
}

func (s *Service) Transfer(ctx context.Context, from, to string, cents int64) error {
	return s.uow.Do(ctx, func(a Accounts) error {
		if err := a.Debit(ctx, from, cents); err != nil {
			return err
		}
		return a.Credit(ctx, to, cents)
	})
}

// package pgbank
func (u UoW) Do(ctx context.Context, fn func(bank.Accounts) error) error {
	return WithTx(ctx, u.Pool, pgx.TxOptions{}, func(tx pgx.Tx) error {
		return fn(NewRepo(tx))
	})
}
```

repository نام constraint را هم به خطای domain تبدیل می‌کند (`non_negative` می‌شود `ErrInsufficient` و `under_limit` می‌شود `ErrLimit`)، مثل [کانفیگ، لاگ و خطا](/fa/posts/go-config-logging-errors/). اجرای سرویس:

```
transfer 100: <nil>
after : alice=900 carol=100 total=1000
transfer 5000: insufficient funds
after : alice=900 carol=100 total=1000
```

## Lost update و FOR UPDATE

تراکنش به‌تنهایی جلوی تداخل دو تراکنش را نمی‌گیرد. دو worker هرکدام موجودی alice را می‌خوانند (1000)، 300 میلی‌ثانیه صبر می‌کنند و `balance + 100` را می‌نویسند. در سطح پیش‌فرض **READ COMMITTED**:

```
plain read      : alice=1100 carol=0 total=1100
SELECT FOR UPDATE: alice=1200 carol=0 total=1200
```

هر دو 1000 را خواندند و هر دو 1100 نوشتند: یک به‌روزرسانی گم شد (**lost update**). خط دوم همان کد با `SELECT balance ... FOR UPDATE` است؛ worker دوم منتظر commit اولی می‌ماند و بعد مقدار تازه را می‌خواند.

## Serializable و retry

راه دیگر `pgx.TxOptions{IsoLevel: pgx.Serializable}` است: در SQL قفلی نمی‌نویسید، ولی Postgres تراکنشی را که نتواند به‌طور امن مرتب کند abort می‌کند:

```
worker 0: <nil>
worker 1: ERROR: could not serialize access due to concurrent update (SQLSTATE 40001)
```

این رفتار عادی است، نه باگ، و جوابش اجرای دوباره‌ی کل تراکنش است:

```go
func retry(fn func() error) error {
	for attempt := 1; ; attempt++ {
		err := fn()
		var pgErr *pgconn.PgError
		if err == nil || !errors.As(err, &pgErr) || pgErr.Code != "40001" || attempt == 5 {
			return err
		}
	}
}
```

با آن، موجودی نهایی 1200 شد و دو worker روی هم 3 تلاش لازم داشتند. تابعی که retry می‌کنید باید دوبار اجرا شدنش بی‌خطر باشد، پس داخلش ایمیل نفرستید.

## Deadlock، کوتاه

دو تراکنش که یکی اول alice و بعد carol را قفل می‌کند و دیگری برعکس، منتظر هم می‌مانند. Postgres تشخیص داد و یکی را کشت:

```
worker 0 (alice then carol): ERROR: deadlock detected (SQLSTATE 40P01)
worker 1 (carol then alice): <nil>
```

ردیف‌ها را همیشه با ترتیب ثابت (مثلاً مرتب بر اساس id) قفل کنید، و با 40P01 مثل 40001 رفتار کنید: retry.

## مشکل N+1

موضوع تراکنش نیست ولی در همین لایه است. 20 سفارش (60 آیتم) را خواندم و تعداد query را با یک tracer در pgx شمردم:

```
N+1          orders=20 items=60 queries=21
= ANY($1)    orders=20 items=60 queries=2
JOIN         orders=20 items=60 queries=1
```

یک query برای سفارش‌ها و یکی به‌ازای هر سفارش همان الگوی N+1 است. `WHERE order_id = ANY($1)` با یک slice همه‌ی آیتم‌ها را یک‌جا می‌آورد و `JOIN` در یک دستور. به‌جای حلقه‌ی query یکی از این دو را بردارید.

## چند نکته که باید حواستان باشد

- تراکنش را کوتاه نگه دارید؛ اتصال را اشغال می‌کند و قفل نگه می‌دارد.
- برای هر عملیات یک راهبرد انتخاب کنید: قفل ردیف (`FOR UPDATE`) یا serializable همراه retry. بی‌دقت ترکیبشان نکنید.
- `RowsAffected()` را چک کنید: `UPDATE` روی ردیفی که وجود ندارد خطا نمی‌دهد.
- هر چیزی که ممکن است دوبار اجرا شود (retry) نباید بیرون از دیتابیس اثر جانبی داشته باشد.
- تعداد query را با tracer سمت کلاینت شمردم؛ `pg_stat_statements` را اینجا امتحان نکردم.

## قدم بعدی

مقاله‌ی بعد: الگوهای concurrency در Go، با worker pool و errgroup.
